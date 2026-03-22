"""
linkedin_company_mcp.py -- Silver Tier LinkedIn Company Page Poster

Playwright-based tool: login once (saves session), open LinkedIn company page
composer with approved post content. Supports optional image attachment.
Human always clicks "Post" -- never auto-posts.

Usage:
    python linkedin_company_mcp.py --setup
        Opens browser for LinkedIn login. Session saved to linkedin_company_session/.

    python linkedin_company_mcp.py --check
        Shows this week's post count and approved drafts ready to publish.

    python linkedin_company_mcp.py --post LI_CO_20260304_post.md
        Opens company page composer pre-filled with approved post.

    python linkedin_company_mcp.py --post LI_CO_20260304_post.md --image path/to/img.png
        Same but also attaches an image.

    python linkedin_company_mcp.py --post LI_CO_20260304_post.md --dry
        Preview post content without opening browser.

Setup (.env):
    LINKEDIN_COMPANY_SLUG=your-company-url-slug   (part after /company/ in URL)
    LINKEDIN_COMPANY_NAME=Your Company Display Name

Rules:
    - Max 2 posts per week (Mon-Sun)
    - File must be in Approved/ folder before --post
    - Human always clicks "Post" -- never auto-posted
    - Session: silver_tier/linkedin_company_session/
    - Log: .linkedin_company_post_log.json
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
logger = logging.getLogger("LI-Company")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT        = Path("silver_tier")
APPROVED     = VAULT / "Approved"
LI_DRAFTS    = VAULT / "LinkedIn_Drafts"
DONE         = VAULT / "Done"
APPROVAL_LOG = VAULT / "Approval_Log.md"
LI_SESSION   = VAULT / "linkedin_company_session"
POST_LOG     = Path(".linkedin_company_post_log.json")

MAX_POSTS_PER_WEEK = 2


# ── Env loader ─────────────────────────────────────────────────────────────────

def _load_env():
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _company_slug() -> str:
    slug = os.environ.get("LINKEDIN_COMPANY_SLUG", "")
    if not slug:
        logger.error("LINKEDIN_COMPANY_SLUG not set.")
        logger.error("Add to .env: LINKEDIN_COMPANY_SLUG=your-company-slug")
        sys.exit(1)
    return slug


def _company_name() -> str:
    return os.environ.get("LINKEDIN_COMPANY_NAME", "")


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

def _read_approved_post(filename: str) -> tuple[str, str | None]:
    """
    Read post body and optional image path from Approved/[filename].
    Returns (post_text, image_path_or_None).
    Strips YAML frontmatter and approval sections.
    """
    filepath = APPROVED / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Not found in Approved/: {filename}")

    raw  = filepath.read_text(encoding="utf-8")
    meta = {}

    # Parse frontmatter
    image_path = None
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
            raw = parts[2].strip()

    image_val = meta.get("image", "none").strip()
    if image_val and image_val.lower() not in ("none", "", "null"):
        image_path = image_val

    # Strip approval checklist and To Post sections
    for marker in ("## Approval Checklist", "## To Post", "\n---\n##"):
        if marker in raw:
            raw = raw[:raw.index(marker)]

    return raw.strip(), image_path


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_setup(session_dir: Path):
    """Open browser for LinkedIn login, save persistent session."""
    from playwright.sync_api import sync_playwright

    logger.info("=== SETUP MODE ===")
    logger.info("Browser khul raha hai -- LinkedIn pe login karo.")
    logger.info("Login hone ke baad feed load hone tak ruko, phir browser band karo.")
    logger.info("Session saved hoga: %s", session_dir)

    session_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(session_dir),
            headless=False,
            slow_mo=300,
            args=["--start-maximized"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        logger.info("Login page khul gaya. Login karo...")
        logger.info("(180s wait -- ya Ctrl+C dabao jab ho jaye)")

        try:
            page.wait_for_selector(".global-nav__nav, .scaffold-layout__main", timeout=180_000)
            logger.info("Login successful! Session saved.")
        except KeyboardInterrupt:
            logger.info("Ctrl+C -- agar login hua tha to session already saved hai.")
        except Exception:
            logger.warning("Timeout -- agar login hua tha to normal mode try karo.")
        finally:
            try:
                import time
                time.sleep(3)
                ctx.close()
            except Exception:
                pass

    logger.info("Ab chalao: python linkedin_company_mcp.py --check")


def cmd_check(vault: Path):
    """Show this week's company post count and approved drafts."""
    log        = _load_post_log()
    week_posts = _posts_this_week(log)
    remaining  = MAX_POSTS_PER_WEEK - len(week_posts)

    slug = os.environ.get("LINKEDIN_COMPANY_SLUG", "(not set -- add to .env)")
    name = os.environ.get("LINKEDIN_COMPANY_NAME", "")

    print("\nLinkedIn Company Page Posting Status")
    print("-" * 40)
    print(f"Company   : {name or slug}")
    print(f"This week : {len(week_posts)}/{MAX_POSTS_PER_WEEK} posts")
    print(f"Remaining : {remaining} slot(s)")

    if week_posts:
        print("\nPosted this week:")
        for entry in week_posts:
            dt = entry.get("posted_at", "?")[:16]
            print(f"  {dt}  |  {entry.get('filename', '?')}  |  {entry.get('chars', '?')} chars")

    approved_dir = vault / "Approved"
    if approved_dir.exists():
        approved = sorted(approved_dir.glob("LI_CO_*.md"))
        if approved:
            print(f"\nApproved and ready to post ({len(approved)}):")
            for f in approved:
                print(f"  python linkedin_company_mcp.py --post {f.name}")
        else:
            print("\nNo approved company posts. Move LI_CO_*.md from Pending_Approval/ to Approved/.")

    pending_dir = vault / "Pending_Approval"
    if pending_dir.exists():
        pending = sorted(pending_dir.glob("LI_CO_*.md"))
        if pending:
            print(f"\nAwaiting review in Pending_Approval/ ({len(pending)}):")
            for f in pending:
                print(f"  {f.name}")

    print()


def cmd_post(filename: str, session_dir: Path, vault: Path,
             image_path: str | None = None, dry: bool = False):
    """Open company page composer with approved post. Enforce weekly limit."""

    # Weekly limit
    log        = _load_post_log()
    week_posts = _posts_this_week(log)

    if len(week_posts) >= MAX_POSTS_PER_WEEK:
        print(f"\nWEEKLY LIMIT REACHED: {MAX_POSTS_PER_WEEK}/{MAX_POSTS_PER_WEEK} posts this week.")
        print("Wait until next Monday, or correct .linkedin_company_post_log.json manually.")
        for entry in week_posts:
            print(f"  {entry.get('posted_at','?')[:16]}  |  {entry.get('filename','?')}")
        sys.exit(1)

    remaining = MAX_POSTS_PER_WEEK - len(week_posts)
    print(f"\nWeekly slots remaining: {remaining}/{MAX_POSTS_PER_WEEK}")

    # Read post
    try:
        post_text, meta_image = _read_approved_post(filename)
    except FileNotFoundError as e:
        logger.error("%s", e)
        logger.error("Move the file to Approved/ before running --post.")
        sys.exit(1)

    # CLI --image overrides frontmatter image
    final_image = image_path or meta_image
    char_count  = len(post_text)

    if char_count > 3000:
        logger.error("Post is %d chars. LinkedIn hard limit is 3000. Shorten it.", char_count)
        sys.exit(1)

    # Preview
    print("\n=== COMPANY POST PREVIEW ===")
    print(f"File      : {filename}")
    print(f"Characters: {char_count}/1300")
    print(f"Image     : {final_image or 'none'}")
    print("-" * 45)
    print(post_text[:600] + ("..." if len(post_text) > 600 else ""))
    print("-" * 45)

    if dry:
        print("\nDRY RUN -- no browser opened.")
        return

    # Session check
    if not session_dir.exists() or not any(session_dir.iterdir()):
        logger.error("LinkedIn company session nahi mila!")
        logger.error("Run: python linkedin_company_mcp.py --setup")
        sys.exit(1)

    # Image check
    if final_image:
        img = Path(final_image)
        if not img.exists():
            logger.warning("Image file not found: %s -- posting without image.", final_image)
            final_image = None

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed.")
        logger.error("Run: uv pip install playwright && uv run python -m playwright install chromium")
        sys.exit(1)

    slug = _company_slug()
    logger.info("Opening LinkedIn Company Page (slug: %s)...", slug)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(session_dir),
            headless=False,
            slow_mo=400,
            args=["--start-maximized"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # ── Strategy 1: Company admin feed page ──────────────────────────────
        admin_url = f"https://www.linkedin.com/company/{slug}/admin/feed/posts/"
        logger.info("Trying company admin page: %s", admin_url)
        page.goto(admin_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Detect session expiry
        if "login" in page.url or "signup" in page.url:
            logger.error("Session expired. Run: python linkedin_company_mcp.py --setup")
            ctx.close()
            sys.exit(1)

        # Try to find "Create a post" on admin page
        admin_post_selectors = [
            'button[aria-label*="Create a post"]',
            'button:has-text("Create a post")',
            '.share-box-feed-entry__trigger',
            '[data-control-name="create_post"]',
            'button[aria-label*="Start a post"]',
            'button:has-text("Start a post")',
        ]
        clicked = False
        for sel in admin_post_selectors:
            try:
                page.wait_for_selector(sel, timeout=4000)
                page.click(sel)
                clicked = True
                logger.info("'Create a post' clicked on company admin page.")
                break
            except Exception:
                continue

        # ── Strategy 2: Feed + identity switcher fallback ────────────────────
        if not clicked:
            logger.info("Admin page button not found -- trying feed + identity switcher.")
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            for sel in ['button[aria-label*="Start a post"]',
                        '.share-box-feed-entry__trigger',
                        'button:has-text("Start a post")']:
                try:
                    page.wait_for_selector(sel, timeout=5000)
                    page.click(sel)
                    clicked = True
                    logger.info("'Start a post' clicked on feed.")
                    break
                except Exception:
                    continue

            if clicked:
                page.wait_for_timeout(1500)
                # Try to switch identity to company page
                company_name = _company_name()
                identity_selectors = [
                    '[data-test-id="share-creation-state__identity-button"]',
                    '.share-creation-state__identity button',
                    'button[aria-label*="identity"]',
                    '[data-control-name="identity_welcome_message"]',
                ]
                for sel in identity_selectors:
                    try:
                        page.wait_for_selector(sel, timeout=3000)
                        page.click(sel)
                        page.wait_for_timeout(1000)
                        # Pick company from dropdown
                        if company_name:
                            page.click(f'span:has-text("{company_name}")')
                        else:
                            # Click first non-personal option
                            opts = page.query_selector_all('[data-test-id="identity-picker-option"]')
                            if len(opts) > 1:
                                opts[1].click()
                        logger.info("Identity switched to company page.")
                        break
                    except Exception:
                        continue

        if not clicked:
            logger.warning("Could not open post composer automatically.")
            logger.warning("Please open LinkedIn manually and paste the post.")

        page.wait_for_timeout(2000)

        # ── Type post text ────────────────────────────────────────────────────
        composer_selectors = [
            '.ql-editor[data-placeholder]',
            '[aria-label="Text editor for creating content"]',
            '[data-placeholder="What do you want to talk about?"]',
            'div.editor-content div[contenteditable="true"]',
            'div[role="textbox"]',
        ]
        typed = False
        for sel in composer_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.click(sel)
                page.keyboard.type(post_text, delay=15)
                typed = True
                logger.info("Post text typed into composer (%d chars).", char_count)
                break
            except Exception:
                continue

        if not typed:
            logger.warning("Could not type into composer. Copy-paste manually:")
            print("\n--- COPY THIS POST ---")
            print(post_text)
            print("--- END ---\n")

        # ── Attach image if provided ──────────────────────────────────────────
        if final_image and typed:
            try:
                img_btn_selectors = [
                    '[aria-label*="Add a photo"]',
                    'button[aria-label*="image"]',
                    '[data-control-name="add_photo"]',
                    'button:has-text("Add a photo")',
                ]
                for sel in img_btn_selectors:
                    try:
                        page.wait_for_selector(sel, timeout=3000)
                        with page.expect_file_chooser() as fc_info:
                            page.click(sel)
                        file_chooser = fc_info.value
                        file_chooser.set_files(final_image)
                        logger.info("Image attached: %s", final_image)
                        break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning("Image attach failed: %s -- post text still ready.", e)

        print("\n" + "=" * 60)
        print("  COMPANY POST PRE-FILLED.")
        print("  REVIEW, THEN CLICK 'POST' TO PUBLISH ON COMPANY PAGE.")
        print("  Close browser WITHOUT clicking Post to cancel.")
        print("=" * 60 + "\n")

        # Wait up to 10 min for human to review
        page.wait_for_timeout(600_000)
        ctx.close()

    # ── Log + move files ──────────────────────────────────────────────────────
    log.append({
        "filename":  filename,
        "posted_at": datetime.now().isoformat(),
        "chars":     char_count,
        "image":     final_image or "none",
    })
    _save_post_log(log)

    if APPROVAL_LOG.exists():
        try:
            with open(APPROVAL_LOG, "a", encoding="utf-8") as lf:
                lf.write(
                    f"| {datetime.now().strftime('%Y-%m-%d %H:%M')} "
                    f"| {filename} | linkedin_company_posted | company_page"
                    f" | composer_opened_{char_count}chars |\n"
                )
        except Exception:
            pass

    src = vault / "Approved" / filename
    if src.exists():
        DONE.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(DONE / filename))
        logger.info("Moved %s >> Done/", filename)

    slots_left = MAX_POSTS_PER_WEEK - len(week_posts) - 1
    print(f"Logged. {slots_left} company posting slot(s) remaining this week.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    _load_env()

    parser = argparse.ArgumentParser(
        description="Silver Tier -- LinkedIn Company Page Poster"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--setup", action="store_true",
        help="Open browser for LinkedIn login (first-time, saves session)"
    )
    group.add_argument(
        "--check", action="store_true",
        help="Show weekly post count and approved company drafts"
    )
    group.add_argument(
        "--post", metavar="FILENAME",
        help="Post an approved draft (file must be in Approved/)"
    )
    parser.add_argument(
        "--image", metavar="PATH",
        help="Path to image file to attach (use with --post)"
    )
    parser.add_argument(
        "--vault", default="silver_tier",
        help="Vault folder path (default: silver_tier)"
    )
    parser.add_argument(
        "--dry", action="store_true",
        help="Preview post without opening browser (use with --post)"
    )
    args = parser.parse_args()

    vault       = Path(args.vault)
    session_dir = vault / "linkedin_company_session"

    try:
        if args.setup:
            cmd_setup(session_dir)
        elif args.check:
            cmd_check(vault)
        elif args.post:
            cmd_post(
                filename=args.post,
                session_dir=session_dir,
                vault=vault,
                image_path=args.image,
                dry=args.dry,
            )
    except KeyboardInterrupt:
        print("\nBand kar diya.")


if __name__ == "__main__":
    main()
