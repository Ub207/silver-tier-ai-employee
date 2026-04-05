"""
full_auto_mode.py — Silver Tier Full Automation Orchestrator

Combines all watchers + auto-approver + approval executor into one script.
Run this once to automate everything.

Features:
  ✅ Gmail watcher → creates action files
  ✅ WhatsApp watcher → detects urgent messages  
  ✅ Auto-approver → classifies emails (archive/approve/human)
  ✅ Approval executor → sends approved emails automatically
  ✅ LinkedIn scheduler → posts on schedule (with approval)

Safety Rules (NEVER bypass):
  ❌ WhatsApp replies → ALWAYS need human click (no business API)
  ❌ LinkedIn posts → ALWAYS need human approval before posting
  ❌ Financial flags (PKR 10,000+) → ALWAYS need human approval
  ❌ High/critical priority → ALWAYS need human approval

Usage:
    python full_auto_mode.py              # run all watchers continuously
    python full_auto_mode.py --email      # email watcher only
    python full_auto_mode.py --whatsapp   # WhatsApp watcher only
    python full_auto_mode.py --linkedin   # LinkedIn scheduler only
    python full_auto_mode.py --once       # process once and exit
"""

import os
import sys
import io
import time
import argparse
import logging
import threading
import signal
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT = Path("silver_tier")
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / f"full_auto_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("FullAuto")

# Import watchers and processors
sys.path.insert(0, str(Path(__file__).parent))

try:
    from gmail_watcher import GmailWatcher, _load_env as gmail_load_env
    # Import auto_approver functions directly to avoid stdout issue
    import auto_approver
    from approval_executor import scan_approved, load_seen as executor_load_seen, save_seen as executor_save_seen
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)

# ── Control flags ─────────────────────────────────────────────────────────────

STOP_EVENT = threading.Event()


def signal_handler(sig, frame):
    logger.info("\nCtrl+C detected — stopping all watchers...")
    STOP_EVENT.set()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ── Email Automation ───────────────────────────────────────────────────────────

def run_gmail_watcher(vault_path: Path, address: str, password: str, interval: int = 180):
    """Poll Gmail and create action files."""
    watcher = GmailWatcher(vault_path, address, password)
    logger.info(f"Gmail Watcher started for {address} (polling every {interval}s)")
    
    while not STOP_EVENT.is_set():
        try:
            count = watcher.check_once()
            if count > 0:
                logger.info(f"✓ {count} new email(s) saved to Needs_Action/")
        except Exception as e:
            logger.error(f"Gmail Watcher error: {e}")
        
        # Sleep in small increments to respond to stop signal faster
        for _ in range(interval):
            if STOP_EVENT.is_set():
                break
            time.sleep(1)


def run_auto_approver(pending_path: Path, interval: int = 30):
    """Auto-classify pending files and move to Approved/Done."""
    seen = auto_approver.load_seen()
    logger.info(f"Auto-Approver started (polling every {interval}s)")
    
    while not STOP_EVENT.is_set():
        try:
            results = auto_approver.scan(seen, dry=False)
            if results:
                archived = sum(1 for r in results if r.get("decision") == "archive")
                approved = sum(1 for r in results if r.get("decision") == "approve")
                human = sum(1 for r in results if r.get("decision") == "human")
                logger.info(f"✓ Auto-Approver: {archived} archived, {approved} auto-approved, {human} need human")
                auto_approver.save_seen(seen)
        except Exception as e:
            logger.error(f"Auto-Approver error: {e}")
        
        for _ in range(interval):
            if STOP_EVENT.is_set():
                break
            time.sleep(1)


def run_approval_executor(approved_path: Path, interval: int = 20):
    """Execute approved actions (send emails, post LinkedIn, log WA)."""
    seen = executor_load_seen()
    logger.info(f"Approval Executor started (polling every {interval}s)")
    
    while not STOP_EVENT.is_set():
        try:
            results = scan_approved(seen, dry=False)
            if results:
                ok = sum(1 for r in results if r.get("status") in ("sent", "posted", "logged"))
                error = sum(1 for r in results if r.get("status") == "error")
                if ok > 0 or error > 0:
                    logger.info(f"✓ Approval Executor: {ok} executed, {error} error(s)")
                    executor_save_seen(seen)
        except Exception as e:
            logger.error(f"Approval Executor error: {e}")
        
        for _ in range(interval):
            if STOP_EVENT.is_set():
                break
            time.sleep(1)


# ── WhatsApp Automation ────────────────────────────────────────────────────────

def run_whatsapp_watcher():
    """
    WhatsApp watcher runs in a separate process due to Playwright.
    This function just monitors the Needs_Action folder for new WA files.
    """
    from whatsapp_watcher import KEYWORDS, NEEDS_ACTION, SESSION_DIR, cleanup_before_restart, acquire_pid_lock
    
    logger.info("WhatsApp Watcher: Use 'python whatsapp_watcher.py' in a separate terminal")
    logger.info("This script monitors WA files created by whatsapp_watcher.py")
    
    # The actual WhatsApp watching is done by whatsapp_watcher.py
    # This function just logs that it should be running separately


# ── LinkedIn Automation ────────────────────────────────────────────────────────

def run_linkedin_scheduler():
    """
    LinkedIn scheduler checks Business_Goals.md for posting schedule.
    Creates drafts and moves to Pending_Approval for human review.
    """
    logger.info("LinkedIn Scheduler: Use 'python linkedin_company_mcp.py' or 'python linkedin_personal_mcp.py'")
    logger.info("Drafts are created in LinkedIn_Drafts/ → Pending_Approval/ → human approves → auto-post")


# ── Main Orchestrator ──────────────────────────────────────────────────────────

def run_email_automation():
    """Run email-related automation threads."""
    from gmail_watcher import _load_env as gmail_env
    
    gmail_env()
    address = os.environ.get("EMAIL_ADDRESS", "")
    password = os.environ.get("EMAIL_APP_PASSWORD", "")
    
    if not address or not password:
        logger.error("EMAIL_ADDRESS or EMAIL_APP_PASSWORD not set in .env")
        return
    
    threads = [
        threading.Thread(target=run_gmail_watcher, args=(VAULT, address, password, 180), daemon=True),
        threading.Thread(target=run_auto_approver, args=(VAULT / "Pending_Approval", 30), daemon=True),
        threading.Thread(target=run_approval_executor, args=(VAULT / "Approved", 20), daemon=True),
    ]
    
    for t in threads:
        t.start()
    
    logger.info("✓ Email automation started (Gmail → Auto-Approve → Send)")
    
    while not STOP_EVENT.is_set():
        time.sleep(1)


def run_whatsapp_automation():
    """Run WhatsApp watcher (separate process)."""
    logger.info("=" * 60)
    logger.info("WhatsApp Automation requires separate process:")
    logger.info("  python whatsapp_watcher.py")
    logger.info("=" * 60)
    
    # Monitor for WA files and log status
    wa_path = VAULT / "Needs_Action"
    while not STOP_EVENT.is_set():
        wa_files = list(wa_path.glob("WA_*.md"))
        if wa_files:
            logger.info(f"✓ {len(wa_files)} WhatsApp message(s) waiting in Needs_Action/")
        time.sleep(60)


def run_linkedin_automation():
    """Run LinkedIn automation."""
    logger.info("=" * 60)
    logger.info("LinkedIn Automation:")
    logger.info("  Company Page: python linkedin_company_mcp.py")
    logger.info("  Personal:     python linkedin_personal_mcp.py")
    logger.info("=" * 60)
    
    # Monitor LinkedIn drafts
    li_path = VAULT / "LinkedIn_Drafts"
    while not STOP_EVENT.is_set():
        li_files = list(li_path.glob("LI_*.md"))
        if li_files:
            logger.info(f"✓ {len(li_files)} LinkedIn draft(s) ready")
        time.sleep(60)


def run_all_automation():
    """Run all automation threads."""
    logger.info("=" * 60)
    logger.info("🚀 SILVER TIER FULL AUTOMATION STARTED")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Active Automation:")
    logger.info("  ✅ Gmail → Auto-classify → Auto-send (non-financial)")
    logger.info("  ⚠️  WhatsApp → Auto-detect → Human approves reply")
    logger.info("  ⚠️  LinkedIn → Auto-draft → Human approves → Auto-post")
    logger.info("")
    logger.info("Safety Rules (NEVER bypassed):")
    logger.info("  ❌ WhatsApp replies → ALWAYS need human click")
    logger.info("  ❌ LinkedIn posts → ALWAYS need human approval")
    logger.info("  ❌ Financial flags → ALWAYS need human approval")
    logger.info("=" * 60)
    logger.info("")
    
    threads = []
    
    # Email automation
    from gmail_watcher import _load_env as gmail_env
    gmail_env()
    address = os.environ.get("EMAIL_ADDRESS", "")
    password = os.environ.get("EMAIL_APP_PASSWORD", "")
    
    if address and password:
        threads.append(threading.Thread(target=run_gmail_watcher, args=(VAULT, address, password, 180), daemon=True))
        threads.append(threading.Thread(target=run_auto_approver, args=(VAULT / "Pending_Approval", 30), daemon=True))
        threads.append(threading.Thread(target=run_approval_executor, args=(VAULT / "Approved", 20), daemon=True))
        logger.info("✓ Email automation threads started")
    else:
        logger.warning("⚠️  Email credentials not set — skipping email automation")
    
    # WhatsApp monitoring (actual watcher runs separately)
    threads.append(threading.Thread(target=run_whatsapp_automation, daemon=True))
    logger.info("✓ WhatsApp monitoring started (run 'python whatsapp_watcher.py' for full functionality)")
    
    # LinkedIn monitoring
    threads.append(threading.Thread(target=run_linkedin_automation, daemon=True))
    logger.info("✓ LinkedIn monitoring started")
    
    # Start all threads
    for t in threads:
        t.start()
    
    # Wait for stop signal
    while not STOP_EVENT.is_set():
        time.sleep(1)
    
    logger.info("Stopping all automation...")


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Silver Tier Full Automation Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python full_auto_mode.py              # Run all automation
  python full_auto_mode.py --email      # Email automation only
  python full_auto_mode.py --whatsapp   # WhatsApp monitoring only
  python full_auto_mode.py --linkedin   # LinkedIn monitoring only
  python full_auto_mode.py --once       # Process once and exit
        """
    )
    
    parser.add_argument("--email", action="store_true", help="Run email automation only")
    parser.add_argument("--whatsapp", action="store_true", help="Run WhatsApp monitoring only")
    parser.add_argument("--linkedin", action="store_true", help="Run LinkedIn monitoring only")
    parser.add_argument("--once", action="store_true", help="Process once and exit (no continuous loop)")
    
    args = parser.parse_args()
    
    # Load environment
    from gmail_watcher import _load_env as gmail_env
    gmail_env()
    
    if args.once:
        logger.info("Processing once (no continuous loop)...")
        
        # Process Gmail once
        address = os.environ.get("EMAIL_ADDRESS", "")
        password = os.environ.get("EMAIL_APP_PASSWORD", "")
        if address and password:
            watcher = GmailWatcher(VAULT, address, password)
            count = watcher.check_once()
            logger.info(f"✓ Gmail: {count} new email(s) processed")
        
        # Run auto-approver once
        seen = approver_load_seen()
        results = auto_approver_scan(seen, dry=False)
        if results:
            approver_save_seen(seen)
            logger.info(f"✓ Auto-Approver: {len(results)} file(s) classified")
        
        # Run approval executor once
        seen = executor_load_seen()
        results = scan_approved(seen, dry=False)
        if results:
            executor_save_seen(seen)
            ok = sum(1 for r in results if r.get("status") in ("sent", "posted", "logged"))
            logger.info(f"✓ Approval Executor: {ok} action(s) executed")
        
        logger.info("Done.")
        return
    
    # Continuous mode
    if args.email:
        run_email_automation()
    elif args.whatsapp:
        run_whatsapp_automation()
    elif args.linkedin:
        run_linkedin_automation()
    else:
        run_all_automation()


if __name__ == "__main__":
    main()
