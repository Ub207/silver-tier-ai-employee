"""
run_all.py — Silver Tier process launcher (no PM2/Node.js required)

Starts WhatsApp Watcher as a background subprocess and runs
workflow_runner every 5 minutes in the foreground loop.

Usage:
    python run_all.py                  # start all
    python run_all.py --no-watcher     # only run workflow loop (no WA watcher)
    python run_all.py --once           # run workflow_runner once and exit
"""

import sys
import time
import subprocess
import argparse
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("SilverTier")

VAULT = "silver_tier"
PYTHON = sys.executable
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

WORKFLOW_INTERVAL  = 300    # seconds between workflow_runner runs (5 min)
LINKEDIN_INTERVAL  = 86400  # seconds between LinkedIn scheduler checks (24 hrs)


WA_LOCKFILE = Path("silver_tier/silver_tier/whatsapp_session/lockfile")

def _clear_wa_lockfile():
    """Delete stale WhatsApp session lock files."""
    for lock in [WA_LOCKFILE, WA_LOCKFILE.parent / "Default" / "LOCK"]:
        if lock.exists():
            try:
                lock.unlink()
                logger.info(f"Stale lock deleted: {lock.name}")
            except Exception as e:
                logger.warning(f"Could not delete {lock.name}: {e}")


def start_watcher() -> subprocess.Popen:
    """Launch whatsapp_watcher.py in its own console window (needed for browser)."""
    _clear_wa_lockfile()
    logger.info("Starting WhatsApp Watcher (new console window)")
    # CREATE_NEW_CONSOLE gives the subprocess its own window — required for Playwright
    proc = subprocess.Popen(
        [PYTHON, "whatsapp_watcher.py"],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    logger.info(f"WhatsApp Watcher PID: {proc.pid}")
    return proc


def start_filesystem_watcher() -> subprocess.Popen:
    """Launch filesystem_watcher.py as a non-blocking subprocess."""
    log_path = LOG_DIR / "filesystem_watcher.log"
    logger.info(f"Starting Filesystem Watcher (logs -> {log_path})")
    with open(log_path, "a", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            [PYTHON, "filesystem_watcher.py", "--vault", VAULT],
            stdout=lf,
            stderr=lf,
        )
    logger.info(f"Filesystem Watcher PID: {proc.pid}")
    return proc


def start_gmail_watcher() -> subprocess.Popen:
    """Launch gmail_watcher.py as a non-blocking subprocess (if credentials exist)."""
    import os
    env_path = Path(".env")
    has_creds = False
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        has_creds = "EMAIL_ADDRESS=" in content and ("EMAIL_APP_PASSWORD=" in content or "EMAIL_PASSWORD=" in content)
    if not has_creds and not (os.environ.get("EMAIL_ADDRESS") and (os.environ.get("EMAIL_APP_PASSWORD") or os.environ.get("EMAIL_PASSWORD"))):
        logger.info("Gmail Watcher skipped (EMAIL_ADDRESS / EMAIL_APP_PASSWORD not set in .env)")
        return None

    log_path = LOG_DIR / "gmail_watcher.log"
    logger.info(f"Starting Gmail Watcher (logs -> {log_path})")
    with open(log_path, "a", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            [PYTHON, "gmail_watcher.py", "--vault", VAULT],
            stdout=lf,
            stderr=lf,
        )
    logger.info(f"Gmail Watcher PID: {proc.pid}")
    return proc


def start_auto_approver() -> subprocess.Popen:
    """Launch auto_approver.py as a non-blocking subprocess."""
    log_path = LOG_DIR / "auto_approver.log"
    logger.info(f"Starting Auto Approver (logs -> {log_path})")
    with open(log_path, "a", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            [PYTHON, "auto_approver.py"],
            stdout=lf,
            stderr=lf,
        )
    logger.info(f"Auto Approver PID: {proc.pid}")
    return proc


def start_approval_executor() -> subprocess.Popen:
    """Launch approval_executor.py as a non-blocking subprocess."""
    log_path = LOG_DIR / "approval_executor.log"
    logger.info(f"Starting Approval Executor (logs -> {log_path})")
    with open(log_path, "a", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            [PYTHON, "approval_executor.py"],
            stdout=lf,
            stderr=lf,
        )
    logger.info(f"Approval Executor PID: {proc.pid}")
    return proc


def start_inbox_planner() -> subprocess.Popen:
    """Launch inbox_planner.py as a non-blocking subprocess."""
    log_path = LOG_DIR / "inbox_planner.log"
    logger.info(f"Starting Inbox Planner (logs -> {log_path})")
    with open(log_path, "a", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            [PYTHON, "inbox_planner.py"],
            stdout=lf,
            stderr=lf,
        )
    logger.info(f"Inbox Planner PID: {proc.pid}")
    return proc


def run_workflow():
    """Run workflow_runner.py once, wait for it to finish."""
    log_path = LOG_DIR / "workflow_runner.log"
    logger.info("Running workflow_runner.py ...")
    with open(log_path, "a", encoding="utf-8") as lf:
        lf.write(f"\n\n--- Run at {datetime.now().isoformat()} ---\n")
        result = subprocess.run(
            [PYTHON, "workflow_runner.py"],
            stdout=lf,
            stderr=lf,
        )
    if result.returncode != 0:
        logger.warning(f"workflow_runner.py exited with code {result.returncode}")
    else:
        logger.info("Workflow run complete.")


def run_linkedin_scheduler(type_key: str = "personal"):
    """Run linkedin_scheduler.py for the given type (skips if a recent draft already exists)."""
    log_path = LOG_DIR / f"linkedin_scheduler_{type_key}.log"
    logger.info("Running linkedin_scheduler.py --type %s ...", type_key)
    with open(log_path, "a", encoding="utf-8") as lf:
        lf.write(f"\n\n--- Run at {datetime.now().isoformat()} ---\n")
        result = subprocess.run(
            [PYTHON, "linkedin_scheduler.py", "--type", type_key],
            stdout=lf,
            stderr=lf,
        )
    if result.returncode != 0:
        logger.warning(f"linkedin_scheduler.py --type {type_key} exited with code {result.returncode}")
    else:
        logger.info("LinkedIn %s scheduler run complete.", type_key)


def main():
    parser = argparse.ArgumentParser(description="Silver Tier — Run All")
    parser.add_argument("--no-watcher", action="store_true",
                        help="Skip WhatsApp Watcher (only run workflow loop)")
    parser.add_argument("--once", action="store_true",
                        help="Run workflow_runner once and exit (no loop)")
    args = parser.parse_args()

    watcher_proc      = None
    fs_watcher        = None
    gmail_watcher     = None
    inbox_planner     = None
    auto_approver     = None
    approval_executor = None

    if not args.no_watcher and not args.once:
        watcher_proc      = start_watcher()
        fs_watcher        = start_filesystem_watcher()
        gmail_watcher     = start_gmail_watcher()
        inbox_planner     = start_inbox_planner()
        auto_approver     = start_auto_approver()
        approval_executor = start_approval_executor()

    if args.once:
        run_workflow()
        return

    logger.info(f"Workflow loop started (every {WORKFLOW_INTERVAL}s). Ctrl+C to stop.")
    last_linkedin_run = 0  # trigger on first cycle

    try:
        while True:
            # Restart watchers if they crashed
            if watcher_proc and watcher_proc.poll() is not None:
                logger.warning("WhatsApp Watcher crashed -- 15s baad restart ho raha hai ...")
                time.sleep(15)
                watcher_proc = start_watcher()
            if fs_watcher and fs_watcher.poll() is not None:
                logger.warning("Filesystem Watcher crashed -- restarting ...")
                fs_watcher = start_filesystem_watcher()
            if gmail_watcher and gmail_watcher.poll() is not None:
                logger.warning("Gmail Watcher crashed -- restarting ...")
                gmail_watcher = start_gmail_watcher()
            if inbox_planner and inbox_planner.poll() is not None:
                logger.warning("Inbox Planner crashed -- restarting ...")
                inbox_planner = start_inbox_planner()
            if auto_approver and auto_approver.poll() is not None:
                logger.warning("Auto Approver crashed -- restarting ...")
                auto_approver = start_auto_approver()
            if approval_executor and approval_executor.poll() is not None:
                logger.warning("Approval Executor crashed -- restarting ...")
                approval_executor = start_approval_executor()

            run_workflow()

            # LinkedIn scheduler: checks daily (skips if recent draft exists)
            now = time.time()
            if now - last_linkedin_run >= LINKEDIN_INTERVAL:
                run_linkedin_scheduler("personal")
                run_linkedin_scheduler("company")
                last_linkedin_run = now

            logger.info(f"Sleeping {WORKFLOW_INTERVAL}s until next run ...")
            time.sleep(WORKFLOW_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Shutting down ...")
        for proc, name in [
            (watcher_proc, "WhatsApp Watcher"),
            (fs_watcher, "Filesystem Watcher"),
            (gmail_watcher, "Gmail Watcher"),
            (inbox_planner, "Inbox Planner"),
            (auto_approver, "Auto Approver"),
            (approval_executor, "Approval Executor"),
        ]:
            if proc and proc.poll() is None:
                proc.terminate()
                logger.info(f"{name} stopped.")


if __name__ == "__main__":
    main()
