import asyncio
if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.sync_api import sync_playwright
from pathlib import Path
import time
import logging
import sys

LOG_FILE = Path("D:/silver_tier/logs/whatsapp_watcher.log")
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("WA-Watcher")

VAULT_PATH   = Path("D:/silver_tier/silver_tier")
NEEDS_ACTION = VAULT_PATH / "Needs_Action"
SESSION_DIR  = VAULT_PATH / "whatsapp_session"
NEEDS_ACTION.mkdir(exist_ok=True)
SESSION_DIR.mkdir(exist_ok=True)

KEYWORDS = ["urgent", "invoice", "payment", "help", "asap", "bhai", "due", "pending"]

def open_browser(headless=False):
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=headless,
        )
        page = context.new_page()
        page.goto("https://web.whatsapp.com")
        return p, context, page

def setup_mode():
    logger.info("SETUP MODE - Browser khul raha hai, QR scan karo...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,  # visible browser
        )
        page = context.new_page()
        page.goto("https://web.whatsapp.com")
        logger.info("WhatsApp Web khul gaya. QR scan karo. 60 second hai...")
        page.wait_for_timeout(60000)  # 60 sec to scan QR
        logger.info("Session save ho gaya. Ab --setup ke bina chalao.")
        context.close()

def watch_mode():
    logger.info("Watch mode start - browser khul raha hai, band mat karna")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
            args=[
                "--start-maximized",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-sandbox",
            ],
        )
        page = context.new_page()
        page.goto("https://web.whatsapp.com")
        logger.info("WhatsApp Web load ho raha hai...")

        # Wait for WhatsApp to fully load — try multiple selectors
        # WA Web now uses role="row" inside a role="grid" (virtual scroll)
        CHAT_SELECTORS = [
            'div[aria-label="Chat list"] div[role="row"]',
            'div[role="grid"] div[role="row"]',
            'div[role="row"]',
            '[data-testid="cell-frame-container"]',
            'div[role="listitem"]',
        ]
        loaded = False
        for sel in CHAT_SELECTORS:
            try:
                page.wait_for_selector(sel, timeout=10000)
                logger.info(f"Chats load ho gaye (selector: {sel})")
                loaded = True
                break
            except Exception:
                continue

        if not loaded:
            logger.warning("Chat selectors nahi mile -- 15s aur wait karta hoon")
            page.wait_for_timeout(15000)

        if page.query_selector('[data-testid="qrcode"]'):
            logger.warning("QR screen - pehle --setup se scan karo")
            context.close()
            return

        logger.info("WhatsApp loaded - monitoring shuru")
        logger.info("Page render ke liye 10s wait kar raha hoon...")
        page.wait_for_timeout(10000)

        page.screenshot(path="D:/silver_tier/wa_debug.png")
        logger.info("Screenshot saved: D:/silver_tier/wa_debug.png")

        seen_files = set()
        counter = 0

        while True:
            # Browser band ho gaya check
            if page.is_closed():
                logger.info("Browser band ho gaya. Watcher stop.")
                break

            try:
                # Scroll to top (ignore errors)
                try:
                    page.evaluate(
                        "var el = document.querySelector('[aria-label=\"Chat list\"]');"
                        "if(el) el.scrollTop = 0;"
                    )
                except Exception:
                    pass
                page.wait_for_timeout(3000)

                if page.is_closed():
                    logger.info("Browser band ho gaya. Watcher stop.")
                    break

                # Try each selector until one returns results
                all_chats = []
                for sel in CHAT_SELECTORS:
                    candidates = page.query_selector_all(sel)
                    if candidates:
                        all_chats = candidates
                        break

                logger.info(f"Chats visible: {len(all_chats)}")

                for chat in all_chats:
                    try:
                        text = chat.inner_text().lower()
                    except Exception:
                        continue
                    if any(kw in text for kw in KEYWORDS):
                        key = text[:100]
                        if key not in seen_files:
                            seen_files.add(key)
                            ts = time.strftime("%Y-%m-%d %H:%M:%S")
                            try:
                                label = (
                                    chat.query_selector('span[dir="auto"][title]') or
                                    chat.query_selector('[data-testid="cell-frame-title"]')
                                )
                                sender = label.get_attribute("title") or label.inner_text() if label else "Unknown"
                            except Exception:
                                sender = "Unknown"
                            content = (
                                f"---\ntype: whatsapp\nfrom: {sender}\n"
                                f"received: {ts}\npriority: high\nstatus: pending\n---\n\n"
                                f"## Message\n{text[:400]}\n\n"
                                f"## Suggested Actions\n- [ ] Reply\n- [ ] Create Plan\n"
                            )
                            counter += 1
                            file_name = f"WA_{int(time.time())}_{counter}.md"
                            (NEEDS_ACTION / file_name).write_text(content, encoding="utf-8")
                            logger.info(f"[SAVED] {sender}: {text[:60]}")

            except Exception as e:
                import traceback
                err_name = type(e).__name__
                if "TargetClosedError" in err_name or "closed" in str(e).lower():
                    logger.info("Browser band ho gaya. Watcher stop.")
                    break
                logger.error(f"Error: {err_name}: {e}")
                logger.error(traceback.format_exc())

            time.sleep(180)

def cleanup_before_restart():
    """Kill Playwright Chromium using WA session, delete all stale lock files."""
    import subprocess as _sp
    # Kill only Playwright's Chromium (those using whatsapp_session), not user's Chrome
    try:
        _sp.run(
            ["wmic", "process", "where",
             "name='chrome.exe' and commandline like '%whatsapp_session%'",
             "call", "terminate"],
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=10
        )
    except Exception:
        pass
    time.sleep(3)
    # Delete all known Chrome lock files
    for lock in [SESSION_DIR / "lockfile", SESSION_DIR / "Default" / "LOCK"]:
        if lock.exists():
            try:
                lock.unlink()
                logger.info(f"Deleted: {lock.name}")
            except Exception:
                pass

PID_FILE = Path("D:/silver_tier/whatsapp_watcher.pid")

def acquire_pid_lock():
    """Return True if this is the only running instance."""
    import os
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 0)  # raises if process not found
            logger.error(f"Already running (PID {old_pid}). Exiting.")
            return False
        except (OSError, ProcessLookupError):
            pass  # old process dead, continue
        except Exception:
            pass
    PID_FILE.write_text(str(os.getpid()))
    return True

if __name__ == "__main__":
    import os
    if "--setup" in sys.argv:
        setup_mode()
    else:
        if not acquire_pid_lock():
            sys.exit(1)
        try:
            while True:
                cleanup_before_restart()
                try:
                    watch_mode()
                except Exception as e:
                    logger.error(f"Watcher crash: {e}")
                logger.info("Watcher band hua -- 15s baad restart ho raha hai...")
                time.sleep(15)
        finally:
            PID_FILE.unlink(missing_ok=True)