"""
run_ai_employee.py — Silver Tier AI Employee Scheduler

Runs on a configurable interval (default: every 5 minutes).
On each cycle:
  1. Checks vault/Inbox for new task files
  2. Runs inbox_planner.py to convert each task into a Plan_*.md
  3. Runs workflow_runner.py to process Needs_Action and route to Pending_Approval
  4. Logs all activity to logs/ai_employee.log

Designed to run as a persistent process (Windows Task Scheduler / PM2 / systemd).

Usage:
    python scripts/run_ai_employee.py                  # run continuously (5-min cycle)
    python scripts/run_ai_employee.py --once           # single cycle then exit
    python scripts/run_ai_employee.py --interval 120   # custom interval in seconds
    python scripts/run_ai_employee.py --dry            # preview only, no file writes
"""

import os
import sys
import io
import time
import argparse
import logging
import subprocess
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Paths ──────────────────────────────────────────────────────────────────────

ROOT    = Path(__file__).resolve().parent.parent   # D:/silver_tier/
VAULT   = ROOT / "silver_tier"                     # Obsidian vault
INBOX   = VAULT / "Inbox"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
INBOX.mkdir(parents=True, exist_ok=True)

PYTHON          = sys.executable
INBOX_PLANNER   = ROOT / "inbox_planner.py"
WORKFLOW_RUNNER = ROOT / "workflow_runner.py"

DEFAULT_INTERVAL  = 300   # 5 minutes
TIMEOUT_PLANNER   = 120   # inbox_planner is fast (no API calls per file by default)
TIMEOUT_WORKFLOW  = 600   # workflow_runner calls Claude API — can take several minutes

# ── Logging ────────────────────────────────────────────────────────────────────

log_file = LOG_DIR / "ai_employee.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("AIEmployee")


# ── Env loader ─────────────────────────────────────────────────────────────────

def load_env():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ── Inbox check ────────────────────────────────────────────────────────────────

def check_inbox() -> list[str]:
    """Return names of .md files currently in the Inbox."""
    if not INBOX.exists():
        return []
    return [f.name for f in sorted(INBOX.glob("*.md"))]


# ── Subprocess runner ──────────────────────────────────────────────────────────

def run_script(script: Path, extra_args: list[str] = None, dry: bool = False,
               timeout: int = None) -> bool:
    """
    Run a Python script as a subprocess, streaming output to log file + console.
    Returns True if exit code is 0, False otherwise.
    """
    if not script.exists():
        logger.warning(f"Script not found, skipping: {script}")
        return False

    cmd = [PYTHON, str(script)] + (extra_args or [])
    if dry:
        cmd.append("--dry")

    effective_timeout = timeout or TIMEOUT_PLANNER
    log_path = LOG_DIR / f"{script.stem}.log"
    logger.info(f"Running: {script.name} {' '.join(extra_args or [])} (timeout: {effective_timeout}s)")

    try:
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"\n\n=== Run at {datetime.now().isoformat()} ===\n")
            result = subprocess.run(
                cmd,
                stdout=lf,
                stderr=lf,
                cwd=str(ROOT),
                timeout=effective_timeout,
            )

        if result.returncode == 0:
            logger.info(f"  {script.name} completed successfully.")
            return True
        else:
            logger.warning(f"  {script.name} exited with code {result.returncode}. See {log_path.name}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"  {script.name} timed out after {effective_timeout}s.")
        return False
    except Exception as e:
        logger.error(f"  {script.name} failed: {e}")
        return False


# ── Single cycle ───────────────────────────────────────────────────────────────

def run_cycle(dry: bool = False) -> dict:
    """
    Execute one full AI Employee cycle:
      1. Check Inbox for new tasks
      2. Run inbox_planner (convert tasks to plans)
      3. Run workflow_runner (route plans to Pending_Approval)

    Returns a summary dict.
    """
    cycle_start = datetime.now()
    logger.info("=" * 60)
    logger.info(f"Cycle started at {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")

    # ── Step 1: Check Inbox ───────────────────────────────────────────────────
    inbox_files = check_inbox()
    logger.info(f"Step 1 — Inbox check: {len(inbox_files)} file(s) found")

    if inbox_files:
        for name in inbox_files:
            logger.info(f"  >> {name}")
    else:
        logger.info("  Inbox is empty.")

    # ── Step 2: Run inbox_planner ─────────────────────────────────────────────
    planner_ok = False
    if inbox_files:
        logger.info("Step 2 — Running task planner ...")
        planner_ok = run_script(INBOX_PLANNER, ["--once"], dry=dry, timeout=TIMEOUT_PLANNER)
    else:
        logger.info("Step 2 — Skipped (no new inbox tasks).")

    # ── Step 3: Run workflow_runner ───────────────────────────────────────────
    logger.info("Step 3 — Running workflow runner ...")
    workflow_ok = run_script(WORKFLOW_RUNNER, dry=dry, timeout=TIMEOUT_WORKFLOW)

    duration = (datetime.now() - cycle_start).total_seconds()
    logger.info(f"Cycle complete in {duration:.1f}s")
    logger.info("=" * 60)

    return {
        "timestamp":    cycle_start.isoformat(),
        "inbox_count":  len(inbox_files),
        "inbox_files":  inbox_files,
        "planner_ok":   planner_ok,
        "workflow_ok":  workflow_ok,
        "duration_sec": round(duration, 1),
    }


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Silver Tier — AI Employee Scheduler")
    parser.add_argument("--once",     action="store_true",
                        help="Run one cycle and exit")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help=f"Seconds between cycles (default: {DEFAULT_INTERVAL})")
    parser.add_argument("--dry",      action="store_true",
                        help="Dry run — preview actions without writing files")
    args = parser.parse_args()

    load_env()

    if args.dry:
        logger.info("DRY RUN MODE -- no files will be written")

    logger.info("Silver Tier AI Employee Scheduler starting ...")
    logger.info(f"  Vault     : {VAULT}")
    logger.info(f"  Inbox     : {INBOX}")
    logger.info(f"  Log file  : {log_file}")
    logger.info(f"  Interval  : {args.interval}s")

    if args.once:
        run_cycle(dry=args.dry)
        return

    logger.info(f"Running continuously. Press Ctrl+C to stop.")
    cycle_count = 0

    try:
        while True:
            cycle_count += 1
            logger.info(f"Cycle #{cycle_count}")
            run_cycle(dry=args.dry)
            logger.info(f"Sleeping {args.interval}s until next cycle ...")
            time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info(f"Scheduler stopped after {cycle_count} cycle(s).")


if __name__ == "__main__":
    main()
