"""
linkedin_personal_mcp.py -- Silver Tier Personal LinkedIn Poster

Playwright-based tool: login once (saves session), open LinkedIn composer
with approved post content. Human always clicks "Post" — never auto-posts.

Usage:
    python linkedin_personal_mcp.py --setup
        Opens browser for manual LinkedIn login. Session saved to linkedin_session/.

    python linkedin_personal_mcp.py --check
        Shows this week's post count and files ready to post.

    python linkedin_personal_mcp.py --post LI_PERSONAL_20260304_my_post.md
        Opens LinkedIn composer pre-filled with approved post content.

    python linkedin_personal_mcp.py --post LI_PERSONAL_20260304_my_post.md --dry
        Preview post content without opening browser.

Rules:
    - Max 2 posts per week (Mon-Sun)
    - File must be in Approved/ folder before --post
    - Human always clicks "Post" -- never auto-posted
    - Session: silver_tier/linkedin_session/
    - Weekly log: .linkedin_post_log.json
"""

import sys
import io
import os
import json
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("LI-Personal")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT            = Path("silver_tier")
APPROVED         = VAULT / "Approved"
LI_DRAFTS        = VAULT / "LinkedIn_Drafts"
PENDING          = VAULT / "Pending_Approval"
DONE             = VAULT / "Done"
APPROVAL_LOG     = VAULT / "Approval_Log.md"
LI_SESSION       = VAULT / "linkedin_session"
POST_LOG         = Path(".linkedin_post_log.json")

MAX_POSTS_PER_WEEK = 2


# ── Post log ───────────────────────────────────────────────────────────────────

def _load_post_log() -> list:
    if POST_LOG.exists():
        try:
            return json.loads(POST_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_post_log(log: list):
    POST_LOG.write_text(json.dumps(log[-100:], indent=2), encoding="utf-8")


def _posts_this_week(log: list) -> list:
    """Return entries from the current Mon-Sun week."""
    today  = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    result = []
    for entry in log:
        try:
            entry_date = datetime.fromisoformat(entry["posted_at"]).date()
            if monday <= entry_date <= sunday:
                result.append(entry)
        except Exception:
            continue
    return result


# ── Post content reader ────────────────────────────────────────────────────────

def _read_approved_post(filename: str) -> str:
    """
    Read post body from Approved/[filename].
    Strips YAML frontmatter and approval checklist — returns clean post text.
    """
    filepath = APPROVED / filename
    if not filepath.exists():
        raise FileNotFoundError(f"File not found in Approved/: {filename}")

    text = filepath.read_text(encoding="utf-8")

    # Strip YAML frontmatter (--- ... ---)
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2].strip()

    # Strip checklist and instructions sections
    for marker in ("## Approval Checklist", "## To Post", "\n---\n##"):
        if marker in text:
            text = text[:text.index(marker)]

    return text.strip()


# ── Commands ───────────────────────────────────────────────────────────────────

CHROME_PROFILE = Path(os.environ.get(
    "CHROME_PROFILE",
    str(Path.home() / "AppData/Local/Google/Chrome/User Data")
))


def cmd_setup(session_dir: Path):
    """Open Playwright browser for LinkedIn manual login — saves session."""
    from playwright.sync_api import sync_playwright
    import time

    session_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== SETUP MODE ===")
    logger.info("Playwright browser khul raha hai.")
    logger.info("LinkedIn pe apna email aur password se LOGIN karo.")
    logger.info("Feed load hone ke baad YAHAN terminal mein Ctrl+C dabao.")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(session_dir),
            headless=False,
            slow_mo=300,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-dev-shm-usage",
            ],
            ignore_default_args=["--enable-automation"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # Hide automation signals
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        logger.info("Login page khul gayi. Apna email/password daalo aur login karo.")
        logger.info("Login hone ke baad yahan terminal mein Ctrl+C dabao.")

        try:
            # Wait up to 3 minutes for user to log in
            page.wait_for_selector(".global-nav__nav, .feed-identity-module", timeout=180_000)
            logger.info("Login successful! Session saved ho raha hai...")
            time.sleep(3)
        except KeyboardInterrupt:
            logger.info("Ctrl+C — session save ho gaya.")
        except Exception:
            logger.warning("Timeout — agar login ho gaya tha to post_now.py try karo.")
        finally:
            try:
                ctx.close()
            except Exception:
                pass

    logger.info("Setup complete! Ab chalao: python post_now.py")


def cmd_check(vault: Path):
    """Show this week's post count and approved drafts ready to post."""
    log        = _load_post_log()
    week_posts = _posts_this_week(log)
    remaining  = MAX_POSTS_PER_WEEK - len(week_posts)

    print("\nLinkedIn Personal Posting Status")
    print("-" * 35)
    print(f"This week : {len(week_posts)}/{MAX_POSTS_PER_WEEK} posts")
    print(f"Remaining : {remaining} slot(s)")

    if week_posts:
        print("\nPosted this week:")
        for entry in week_posts:
            dt = entry.get("posted_at", "?")[:16]
            print(f"  {dt}  |  {entry.get('filename', '?')}  |  {entry.get('chars', '?')} chars")

    approved_dir = vault / "Approved"
    if approved_dir.exists():
        approved = sorted(approved_dir.glob("LI_*.md"))
        if approved:
            print(f"\nApproved and ready to post ({len(approved)}):")
            for f in approved:
                print(f"  python linkedin_personal_mcp.py --post {f.name}")
        else:
            print("\nNo approved posts. Move a file from Pending_Approval/ to Approved/ first.")

    pending_dir = vault / "Pending_Approval"
    if pending_dir.exists():
        pending = sorted(pending_dir.glob("LI_PERSONAL_*.md"))
        if pending:
            print(f"\nAwaiting your review in Pending_Approval/ ({len(pending)}):")
            for f in pending:
                print(f"  {f.name}")

    print()


def cmd_post(filename: str, session_dir: Path, vault: Path, dry: bool = False):
    """Open LinkedIn composer with an approved post. Enforce weekly limit."""

    # Weekly limit check
    log        = _load_post_log()
    week_posts = _posts_this_week(log)

    if len(week_posts) >= MAX_POSTS_PER_WEEK:
        print(f"\nWEEKLY LIMIT REACHED: {MAX_POSTS_PER_WEEK}/{MAX_POSTS_PER_WEEK} posts this week.")
        print("Wait until next Monday, or edit .linkedin_post_log.json to correct errors.")
        for entry in week_posts:
            print(f"  {entry.get('posted_at', '?')[:16]}  |  {entry.get('filename', '?')}")
        sys.exit(1)

    remaining = MAX_POSTS_PER_WEEK - len(week_posts)
    print(f"\nWeekly slots remaining: {remaining}/{MAX_POSTS_PER_WEEK}")

    # Read post content
    try:
        post_text = _read_approved_post(filename)
    except FileNotFoundError as e:
        logger.error("%s", e)
        logger.error("Move the file to Approved/ before running --post.")
        sys.exit(1)

    char_count = len(post_text)

    if char_count > 3000:
        logger.error("Post is %d chars. LinkedIn hard limit is 3000. Shorten it.", char_count)
        sys.exit(1)

    # Preview
    print("\n=== POST PREVIEW ===")
    print(f"File      : {filename}")
    print(f"Characters: {char_count}/1300")
    print("-" * 40)
    preview = post_text[:600]
    print(preview + ("..." if len(post_text) > 600 else ""))
    print("-" * 40)

    if dry:
        print("\nDRY RUN -- no browser opened.")
        return

    # Session check
    if not session_dir.exists() or not any(session_dir.iterdir()):
        logger.error("LinkedIn session nahi mila!")
        logger.error("Pehle chalao: python linkedin_personal_mcp.py --setup")
        sys.exit(1)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed.")
        logger.error("Run: uv pip install playwright && uv run python -m playwright install chromium")
        sys.exit(1)

    logger.info("Opening LinkedIn (headless=False so you can click Post)...")

    with sync_playwright() as p:
        session_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Using Playwright session: %s", session_dir)
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(session_dir),
            headless=False,
            slow_mo=400,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-dev-shm-usage",
            ],
            ignore_default_args=["--enable-automation"],
        )
        # Hide automation signals
        for pg in ctx.pages:
            pg.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        ctx.on("page", lambda pg: pg.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"))
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Check if session expired (redirected to login)
        if "login" in page.url or "signup" in page.url:
            logger.error("Session expired. Run: python linkedin_personal_mcp.py --setup")
            ctx.close()
            sys.exit(1)

        # Click "Start a post"
        start_selectors = [
            'button[aria-label*="Start a post"]',
            '.share-box-feed-entry__trigger',
            'button:has-text("Start a post")',
            '[data-control-name="share.sharebox_text"]',
        ]
        clicked = False
        for sel in start_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.click(sel)
                clicked = True
                logger.info("'Start a post' clicked.")
                break
            except Exception:
                continue

        if not clicked:
            logger.warning("Could not find 'Start a post' button -- manual action needed.")

        page.wait_for_timeout(2000)

        # Type into composer
        composer_selectors = [
            '.ql-editor[data-placeholder]',
            '[aria-label="Text editor for creating content"]',
            '[data-placeholder="What do you want to talk about?"]',
            'div.editor-content div[contenteditable="true"]',
        ]
        typed = False
        for sel in composer_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.click(sel)
                page.keyboard.type(post_text, delay=15)
                typed = True
                logger.info("Post typed into composer (%d chars).", char_count)
                break
            except Exception:
                continue

        if not typed:
            logger.warning("Could not type into composer. Copy-paste manually:")
            print("\n--- COPY THIS ---")
            print(post_text)
            print("--- END ---\n")

        print("\n" + "=" * 55)
        print("  POST PRE-FILLED. REVIEW, THEN CLICK 'POST' BUTTON.")
        print("  Close browser WITHOUT posting to cancel.")
        print("=" * 55 + "\n")

        # Wait up to 10 min for human to review and click Post
        page.wait_for_timeout(600_000)
        ctx.close()

    # Log the composer opening as a post attempt
    log.append({
        "filename": filename,
        "posted_at": datetime.now().isoformat(),
        "chars": char_count,
    })
    _save_post_log(log)

    # Append to Approval_Log.md
    if APPROVAL_LOG.exists():
        try:
            with open(APPROVAL_LOG, "a", encoding="utf-8") as lf:
                lf.write(
                    f"| {datetime.now().strftime('%Y-%m-%d %H:%M')} "
                    f"| {filename} | linkedin_personal_posted | personal_profile"
                    f" | composer_opened_{char_count}chars |\n"
                )
        except Exception:
            pass

    # Move Approved -> Done
    src = vault / "Approved" / filename
    if src.exists():
        DONE.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(DONE / filename))
        logger.info("Moved %s >> Done/", filename)

    slots_left = MAX_POSTS_PER_WEEK - len(week_posts) - 1
    print(f"Logged. {slots_left} posting slot(s) remaining this week.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Silver Tier -- LinkedIn Personal Poster"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--setup", action="store_true",
        help="Open browser for LinkedIn login (first-time, saves session)"
    )
    group.add_argument(
        "--check", action="store_true",
        help="Show this week's post count and approved drafts"
    )
    group.add_argument(
        "--post", metavar="FILENAME",
        help="Post an approved draft (file must be in Approved/)"
    )
    parser.add_argument(
        "--vault", default="silver_tier",
        help="Vault folder path (default: silver_tier)"
    )
    parser.add_argument(
        "--dry", action="store_true",
        help="Preview post content without opening browser (use with --post)"
    )
    args = parser.parse_args()

    vault       = Path(args.vault)
    session_dir = vault / "linkedin_session"

    try:
        if args.setup:
            cmd_setup(session_dir)
        elif args.check:
            cmd_check(vault)
        elif args.post:
            cmd_post(args.post, session_dir, vault, dry=args.dry)
    except KeyboardInterrupt:
        print("\nBand kar diya.")


if __name__ == "__main__":
    main()
