"""
linkedin_mcp.py -- Silver Tier LinkedIn MCP Server

Exposes Claude Code tools for the LinkedIn workflow:
  - list_linkedin_drafts     : list post drafts awaiting review
  - open_linkedin_composer   : open LinkedIn and pre-fill the compose box
  - get_vault_status         : read current Dashboard.md

Setup (one-time):
    Add to .mcp.json at project root (already done).
    Run: claude mcp add linkedin -- python D:/silver_tier/linkedin_mcp.py

Usage:
    Claude Code will call this server automatically via MCP.
    Human still clicks "Post" -- this only pre-fills the composer.

Dependencies:
    pip install mcp playwright
    python -m playwright install chromium
"""

import sys
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime

from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("LinkedInMCP")

# ── Config ────────────────────────────────────────────────────────────────────

VAULT        = Path("D:/silver_tier/silver_tier")
LI_DRAFTS    = VAULT / "LinkedIn_Drafts"
PENDING      = VAULT / "Pending_Approval"
APPROVED     = VAULT / "Approved"
DASHBOARD    = VAULT / "Dashboard.md"
LI_SESSION   = VAULT / "linkedin_session"

mcp = FastMCP("LinkedIn MCP")


# ── Tool 1: list_linkedin_drafts ──────────────────────────────────────────────

@mcp.tool()
def list_linkedin_drafts() -> str:
    """
    List all LinkedIn post drafts in the vault.
    Returns a formatted table of draft and pending files with their status.
    """
    rows = []

    for folder, label in [(LI_DRAFTS, "Draft"), (PENDING, "Pending"), (APPROVED, "Approved")]:
        if not folder.exists():
            continue
        for f in sorted(folder.glob("LI_*.md")):
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            # Quick frontmatter peek
            text = f.read_text(encoding="utf-8", errors="ignore")
            status = "unknown"
            for line in text.splitlines():
                if line.startswith("status:"):
                    status = line.split(":", 1)[1].strip()
                    break
            rows.append(f"| {f.name} | {label} | {status} | {mtime} |")

    if not rows:
        return "No LinkedIn drafts found. Run `python linkedin_scheduler.py` to generate one."

    header = "| File | Folder | Status | Modified |\n|------|--------|--------|----------|\n"
    return header + "\n".join(rows)


# ── Tool 2: open_linkedin_composer ────────────────────────────────────────────

@mcp.tool()
def open_linkedin_composer(post_text: str) -> str:
    """
    Open LinkedIn in a browser and pre-fill the post composer with the given text.
    The browser stays open for the human to review and click 'Post'.
    Never auto-posts -- human must confirm.

    Args:
        post_text: The LinkedIn post content to pre-fill in the composer.
    """
    if not post_text.strip():
        return "ERROR: post_text is empty. Pass the full post content."

    char_count = len(post_text)
    if char_count > 1300:
        return (
            f"ERROR: Post is {char_count} chars (max 1300). "
            "Please shorten it before opening the composer."
        )

    LI_SESSION.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (
            "ERROR: Playwright not installed.\n"
            "Run: pip install playwright && python -m playwright install chromium"
        )

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(LI_SESSION),
                headless=False,           # Must be visible so human can click Post
                slow_mo=500,
                args=["--start-maximized"],
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            logger.info("Navigating to LinkedIn...")
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Click "Start a post" button
            start_post_selectors = [
                'button[aria-label*="Start a post"]',
                '[data-control-name="share.sharebox_text"]',
                '.share-box-feed-entry__trigger',
                'button:has-text("Start a post")',
            ]

            clicked = False
            for sel in start_post_selectors:
                try:
                    page.wait_for_selector(sel, timeout=5000)
                    page.click(sel)
                    clicked = True
                    logger.info("Clicked 'Start a post' button.")
                    break
                except Exception:
                    continue

            if not clicked:
                # Try navigating directly to the share dialog URL
                page.goto("https://www.linkedin.com/sharing/share-offsite/", wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

            # Wait for composer textarea
            page.wait_for_timeout(2000)

            composer_selectors = [
                '.ql-editor[data-placeholder]',
                '[aria-label="Text editor for creating content"]',
                '[data-placeholder="What do you want to talk about?"]',
                '.share-creation-state__editor .ql-editor',
            ]

            for sel in composer_selectors:
                try:
                    page.wait_for_selector(sel, timeout=5000)
                    page.click(sel)
                    page.keyboard.type(post_text, delay=20)
                    logger.info("Post text typed into composer (%d chars).", char_count)
                    break
                except Exception:
                    continue

            # Log to vault
            log_entry = (
                f"| {datetime.now().strftime('%Y-%m-%d %H:%M')} "
                f"| LinkedIn composer opened | {char_count} chars | Human review pending |\n"
            )
            log_path = VAULT / "Approval_Log.md"
            if log_path.exists():
                with open(log_path, "a", encoding="utf-8") as lf:
                    lf.write(log_entry)

            # Keep browser open for 10 minutes for human to review and post
            logger.info("Browser open. Review and click Post. Closing in 10 min if idle.")
            page.wait_for_timeout(600_000)  # 10 minutes

            ctx.close()

        return (
            f"LinkedIn composer opened with {char_count} chars pre-filled.\n"
            "REMINDER: Human must click the 'Post' button. This tool never auto-posts."
        )

    except Exception as e:
        logger.error("Playwright error: %s", e)
        return (
            f"ERROR opening LinkedIn composer: {e}\n\n"
            "If not logged in, run this once to set up the session:\n"
            "  python -c \"from playwright.sync_api import sync_playwright; "
            "p = sync_playwright().start(); "
            "ctx = p.chromium.launch_persistent_context('silver_tier/silver_tier/linkedin_session', headless=False); "
            "input('Login then press Enter'); ctx.close(); p.stop()\""
        )


# ── Tool 3: get_vault_status ──────────────────────────────────────────────────

@mcp.tool()
def get_vault_status() -> str:
    """
    Return the current contents of Dashboard.md so Claude can report system status.
    """
    if DASHBOARD.exists():
        return DASHBOARD.read_text(encoding="utf-8")
    return "Dashboard.md not found. Run `python workflow_runner.py` to create it."


# ── Tool 4: get_post_content ──────────────────────────────────────────────────

@mcp.tool()
def get_post_content(filename: str) -> str:
    """
    Read the content of a specific LinkedIn draft file.

    Args:
        filename: The filename (e.g. LI_20260303_my_post.md)
    """
    for folder in [LI_DRAFTS, PENDING, APPROVED]:
        target = folder / filename
        if target.exists():
            return target.read_text(encoding="utf-8")

    return f"File '{filename}' not found in LinkedIn_Drafts/, Pending_Approval/, or Approved/."


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
