"""
post_linkedin.py — LinkedIn Post skill
Creates a real LinkedIn post using Playwright browser automation.

Usage:
    python post_linkedin.py --text "Your post content here"
    python post_linkedin.py --file path/to/post.md
    python post_linkedin.py --setup   # first-time login + session save

Environment variables required:
    LINKEDIN_EMAIL     — your LinkedIn email
    LINKEDIN_PASSWORD  — your LinkedIn password
"""

import os
import sys
import io
import re
import time
import argparse
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

VAULT          = Path(__file__).resolve().parents[3] / "AI_Employee_Vault"
SESSION_DIR    = VAULT / "linkedin_session"
LOG_DIR        = Path(__file__).resolve().parents[3] / "logs"
MAX_CHARS      = 3000
FEED_URL       = "https://www.linkedin.com/feed/"

LOG_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)


# ── Env loader ─────────────────────────────────────────────────────────────────

def load_env():
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ── Session setup (manual login) ───────────────────────────────────────────────

def setup_session():
    from playwright.sync_api import sync_playwright
    print("Opening browser for manual LinkedIn login ...")
    print("Log in, complete any 2FA, then press Enter here to save your session.")
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=False,
            args=["--start-maximized"],
        )
        page = browser.new_page()
        page.goto("https://www.linkedin.com/login")
        input(">> Press Enter after you have logged in successfully: ")
        browser.close()
    print(f"[OK] Session saved to {SESSION_DIR}")


# ── Login via credentials ──────────────────────────────────────────────────────

def login_with_credentials(page, email: str, password: str):
    print("    Logging in with credentials ...")
    page.goto("https://www.linkedin.com/login", timeout=30000)
    page.wait_for_load_state("networkidle")
    page.fill("#username", email)
    page.fill("#password", password)
    page.click("button[type='submit']")
    page.wait_for_url(re.compile(r"linkedin\.com/(feed|checkpoint|authwall)"), timeout=20000)
    if "checkpoint" in page.url or "authwall" in page.url:
        print("[ERROR] LinkedIn requires additional verification (2FA/CAPTCHA).")
        print("        Run with --setup to log in manually and save your session.")
        sys.exit(1)
    print("    Login successful.")


def is_logged_in(page) -> bool:
    try:
        page.wait_for_selector("div.feed-identity-module", timeout=5000)
        return True
    except Exception:
        return False


# ── Post creation ──────────────────────────────────────────────────────────────

def create_post(page, text: str):
    page.goto(FEED_URL, timeout=30000)
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # Click "Start a post" button
    try:
        start_btn = page.wait_for_selector(
            "button.share-box-feed-entry__trigger, button[aria-label*='post'], div[data-control-name='share.sharebox_create']",
            timeout=10000,
        )
        start_btn.click()
    except Exception:
        screenshot_path = LOG_DIR / f"linkedin_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        page.screenshot(path=str(screenshot_path))
        print("[ERROR] Could not locate the 'Start a post' button on LinkedIn feed.")
        print(f"        Screenshot saved to {screenshot_path}")
        print("        LinkedIn may have updated their UI. Check selectors.")
        sys.exit(1)

    time.sleep(1.5)

    # Type post content into the composer
    try:
        editor = page.wait_for_selector(
            "div.ql-editor, div[contenteditable='true'][data-placeholder]",
            timeout=10000,
        )
        editor.click()
        editor.type(text, delay=20)
    except Exception:
        screenshot_path = LOG_DIR / f"linkedin_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        page.screenshot(path=str(screenshot_path))
        print("[ERROR] Could not locate the post composer editor.")
        print(f"        Screenshot saved to {screenshot_path}")
        sys.exit(1)

    time.sleep(1)

    # Click Post button
    try:
        post_btn = page.wait_for_selector(
            "button.share-actions__primary-action, button[data-control-name='share.post']",
            timeout=10000,
        )
        post_btn.click()
    except Exception:
        screenshot_path = LOG_DIR / f"linkedin_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        page.screenshot(path=str(screenshot_path))
        print("[ERROR] Could not locate the Post submit button.")
        print(f"        Screenshot saved to {screenshot_path}")
        sys.exit(1)

    # Wait for modal to close (post submitted)
    try:
        page.wait_for_selector(
            "div.share-creation-state--processing, div.feed-shared-update-v2",
            timeout=15000,
        )
    except Exception:
        pass  # Post may still have gone through

    time.sleep(2)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Post — Silver Tier AI Employee")
    parser.add_argument("--text",     help="Post content as a string")
    parser.add_argument("--file",     help="Path to .md or .txt file containing post content")
    parser.add_argument("--headless", action="store_true", default=True, help="Run headlessly")
    parser.add_argument("--setup",    action="store_true", help="Manual login + session save")
    args = parser.parse_args()

    load_env()

    if args.setup:
        setup_session()
        return

    if args.text and args.file:
        print("[ERROR] Provide either --text or --file, not both.")
        sys.exit(1)
    if not args.text and not args.file:
        print("[ERROR] Provide post content via --text or --file.")
        sys.exit(1)

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"[ERROR] File not found: {file_path}")
            sys.exit(1)
        post_text = file_path.read_text(encoding="utf-8").strip()
        # Strip markdown frontmatter if present
        if post_text.startswith("---"):
            parts = post_text.split("---", 2)
            if len(parts) >= 3:
                post_text = parts[2].strip()
    else:
        post_text = args.text.strip()

    if not post_text:
        print("[ERROR] Post content is empty.")
        sys.exit(1)

    if len(post_text) > MAX_CHARS:
        print(f"[WARN] Post content truncated from {len(post_text)} to {MAX_CHARS} characters.")
        post_text = post_text[:MAX_CHARS]

    email    = os.environ.get("LINKEDIN_EMAIL", "")
    password = os.environ.get("LINKEDIN_PASSWORD", "")

    session_exists = (SESSION_DIR / "Default").exists() or any(SESSION_DIR.iterdir()) if SESSION_DIR.exists() else False

    if not session_exists and (not email or not password):
        print("[ERROR] No saved session found and LINKEDIN_EMAIL / LINKEDIN_PASSWORD are not set.")
        print("        Run with --setup to log in and save your session, or add credentials to .env.")
        sys.exit(1)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        if session_exists:
            browser = p.chromium.launch_persistent_context(
                str(SESSION_DIR),
                headless=args.headless,
            )
            page = browser.new_page()
        else:
            browser_instance = p.chromium.launch(headless=args.headless)
            browser = browser_instance.new_context()
            page = browser.new_page()

        try:
            page.goto(FEED_URL, timeout=30000)
            page.wait_for_load_state("networkidle")

            if not is_logged_in(page):
                if not email or not password:
                    print("[ERROR] Session expired and no credentials set.")
                    print("        Add LINKEDIN_EMAIL and LINKEDIN_PASSWORD to .env or run --setup.")
                    sys.exit(1)
                login_with_credentials(page, email, password)

            create_post(page, post_text)

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[OK] LinkedIn post published successfully")
            print(f"     Characters : {len(post_text)}")
            print(f"     Posted at  : {now}")

        except SystemExit:
            raise
        except Exception as e:
            screenshot_path = LOG_DIR / f"linkedin_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            try:
                page.screenshot(path=str(screenshot_path))
                print(f"[ERROR] Unexpected error: {e}")
                print(f"        Screenshot saved to {screenshot_path}")
            except Exception:
                print(f"[ERROR] Unexpected error: {e}")
            sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
