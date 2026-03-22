"""
linkedin_scheduler.py -- Silver Tier LinkedIn post draft generator

Automatically generates a LinkedIn post draft using the Claude API,
routes it to Pending_Approval/ for human review before any posting.

Schedule: runs daily via run_all.py / PM2 / Task Scheduler.
Skips generation if a draft was already created within 3 days.

Usage:
    python linkedin_scheduler.py                       # personal, generate if overdue
    python linkedin_scheduler.py --type company        # generate for company page
    python linkedin_scheduler.py --force               # always generate, skip recency check
    python linkedin_scheduler.py --dry                 # preview prompt without calling API
    python linkedin_scheduler.py --type company --force

Requirements:
    ANTHROPIC_API_KEY env var (or in .env file)
"""

import os
import sys
import io
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Fix Windows cp1252 encoding issues (vault files may contain Unicode)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("LinkedInScheduler")

# ── Config ────────────────────────────────────────────────────────────────────

VAULT          = Path("silver_tier")
LI_DRAFTS      = VAULT / "LinkedIn_Drafts"
PENDING        = VAULT / "Pending_Approval"
BUSINESS_GOALS = VAULT / "Business_Goals.md"
DASHBOARD      = VAULT / "Dashboard.md"

POST_INTERVAL_DAYS = 3     # generate a new draft if last one is older than this
MODEL              = "claude-haiku-4-5-20251001"
MAX_TOKENS         = 800

# Post type config
POST_TYPES = {
    "personal": {
        "prefix":   "LI_PERSONAL_",
        "type_val": "linkedin_post_personal",
        "voice":    "personal (use 'I', 'my', first-person founder voice)",
        "script":   "linkedin_personal_mcp.py",
    },
    "company": {
        "prefix":   "LI_CO_",
        "type_val": "linkedin_company_post",
        "voice":    "company (use 'we', 'our clients', company voice)",
        "script":   "linkedin_company_mcp.py",
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_api_key() -> str:
    """Return ANTHROPIC_API_KEY from env, optionally loading from .env file."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return key


def _recent_draft_exists(type_key: str = "personal") -> bool:
    """Return True if a LinkedIn draft for the given type was created within POST_INTERVAL_DAYS."""
    prefix = POST_TYPES[type_key]["prefix"]
    cutoff = datetime.now() - timedelta(days=POST_INTERVAL_DAYS)
    for f in LI_DRAFTS.glob(f"{prefix}*.md"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime > cutoff:
            logger.info("Recent draft found: %s (skip generation)", f.name)
            return True
    return False


def _read_business_goals() -> str:
    if BUSINESS_GOALS.exists():
        return BUSINESS_GOALS.read_text(encoding="utf-8")
    return "Focus: AI automation for founders. Audience: solopreneurs."


def _build_prompt(goals_text: str, type_key: str = "personal") -> str:
    today = datetime.now().strftime("%B %d, %Y")
    voice = POST_TYPES[type_key]["voice"]
    return f"""You are a LinkedIn content writer for a solo founder who builds AI automation systems.
Write in {voice} voice.

Today is {today}.

Here is their Business Goals file:
---
{goals_text}
---

Write ONE LinkedIn post following these rules:
1. Hook (first line): Bold statement, surprising fact, or direct question -- max 12 words
2. Body (3-5 short paragraphs, each 1-3 sentences): Teach ONE useful insight
3. CTA (last line): One clear ask (comment, share, or DM) -- not "I'm excited"
4. Max 1300 characters total
5. Max 3 relevant hashtags at the very end
6. NO "I'm excited to share..." opener
7. Value-first: reader learns something even if they never hire you
8. Rotate through these content pillars: AI Automation, Founder Productivity, Client Case Studies
9. Match the tone: Direct, no fluff, honest, no hype

Output ONLY the post text (no intro, no explanation, no markdown code blocks).
The post should read naturally on LinkedIn."""


OPENROUTER_MODELS_FALLBACK = [
    "google/gemma-3-4b-it:free",
    "qwen/qwen3-4b:free",
    "liquid/lfm-2.5-1.2b-instruct:free",
    "google/gemma-3-12b-it:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]

def _call_openrouter(prompt: str, model: str = None) -> str:
    """Call OpenRouter API (free models available)."""
    import urllib.request, json
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    if not model:
        model = os.environ.get("OPENROUTER_MODEL", OPENROUTER_MODELS_FALLBACK[0])
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/silver-tier-ai",
            "X-Title": "Silver Tier AI Employee",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def _call_openrouter_with_fallback(prompt: str) -> str:
    """Try multiple OpenRouter free models until one works."""
    import time
    primary = os.environ.get("OPENROUTER_MODEL", OPENROUTER_MODELS_FALLBACK[0])
    models  = [primary] + [m for m in OPENROUTER_MODELS_FALLBACK if m != primary]
    for model in models:
        try:
            logger.info("OpenRouter: trying %s...", model)
            result = _call_openrouter(prompt, model)
            logger.info("OpenRouter success: %s", model)
            return result
        except Exception as e:
            logger.warning("OpenRouter %s failed: %s", model, e)
            time.sleep(2)
    raise RuntimeError("All OpenRouter models failed.")


def _call_ollama(prompt: str) -> str:
    """Call local Ollama (llama3.2) to generate post text."""
    import urllib.request, json
    payload = json.dumps({
        "model": "llama3.2",
        "prompt": prompt,
        "stream": False
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["response"].strip()


def _call_ai(prompt: str, api_key: str) -> str:
    """Try OpenRouter → Anthropic → Ollama in order."""
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        try:
            return _call_openrouter_with_fallback(prompt)
        except Exception as e:
            logger.warning("OpenRouter all failed (%s) — trying Anthropic...", e)

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
            message = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text.strip()
        except Exception as e:
            logger.warning("Claude API failed (%s) — trying Ollama...", e)

    try:
        logger.info("Using Ollama (llama3.2)...")
        return _call_ollama(prompt)
    except Exception as e:
        logger.error("Ollama also failed: %s", e)
        raise RuntimeError("All AI engines unavailable (OpenRouter, Claude, Ollama).") from e


def _slug_from_post(text: str) -> str:
    """Extract a short slug from the first line of the post."""
    first_line = text.split("\n")[0][:50]
    slug = "".join(c if c.isalnum() else "_" for c in first_line.lower()).strip("_")
    return slug[:30] or "post"


def _save_draft(post_text: str, type_key: str = "personal") -> tuple[Path, Path]:
    """Save post to LinkedIn_Drafts/ and route a copy to Pending_Approval/."""
    LI_DRAFTS.mkdir(parents=True, exist_ok=True)
    PENDING.mkdir(parents=True, exist_ok=True)

    prefix    = POST_TYPES[type_key]["prefix"]
    type_val  = POST_TYPES[type_key]["type_val"]
    datestamp = datetime.now().strftime("%Y%m%d_%H%M")
    slug      = _slug_from_post(post_text)
    filename  = f"{prefix}{datestamp}_{slug}.md"

    char_count = len(post_text)

    content = f"""---
type: {type_val}
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
status: draft
model: {MODEL}
characters: {char_count}
---

{post_text}

---
## Approval Checklist
- [ ] Hook is compelling (grabs attention in first line)
- [ ] Teaches something useful (value-first)
- [ ] CTA is clear
- [ ] Under 1300 characters ({char_count}/1300)
- [ ] Approved to post

## To Post
Once approved, run `/approval-handler approve {filename}` then paste into LinkedIn manually.
"""

    draft_path   = LI_DRAFTS / filename
    pending_path = PENDING / filename

    draft_path.write_text(content, encoding="utf-8")
    pending_path.write_text(content, encoding="utf-8")

    return draft_path, pending_path


def _update_dashboard(filename: str):
    """Append new LinkedIn draft to Dashboard.md LinkedIn table."""
    if not DASHBOARD.exists():
        return

    dash = DASHBOARD.read_text(encoding="utf-8")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"| {filename} | Auto-generated | draft | {now} |"

    # Replace the "No drafts today" placeholder if present
    if "No drafts today" in dash:
        dash = dash.replace(
            "| -- | -- | -- | No drafts today |",
            entry
        )
    else:
        # Append row after the LinkedIn Drafts table header
        header_marker = "| File | Topic | Status | Created |"
        separator     = "|------|-------|--------|---------|"
        insert_after  = separator
        if insert_after in dash:
            dash = dash.replace(insert_after, insert_after + "\n" + entry, 1)

    DASHBOARD.write_text(dash, encoding="utf-8")
    logger.info("Dashboard updated with new draft.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Silver Tier -- LinkedIn Scheduler")
    parser.add_argument("--type",  choices=["personal", "company"], default="personal",
                        help="Post type: personal (default) or company")
    parser.add_argument("--force", action="store_true",
                        help="Generate even if a recent draft exists")
    parser.add_argument("--dry",   action="store_true",
                        help="Show prompt only, no API call or file writes")
    args = parser.parse_args()

    type_key = args.type
    logger.info("LinkedIn Scheduler started (type: %s)", type_key)

    # Recency check
    if not args.force and not args.dry:
        if _recent_draft_exists(type_key):
            logger.info("No new %s draft needed. Use --force to override.", type_key)
            return

    # Load API key
    api_key = _load_api_key()
    if not api_key and not args.dry:
        logger.error("ANTHROPIC_API_KEY not set. Add it to your .env file.")
        logger.error("  echo ANTHROPIC_API_KEY=sk-ant-... >> .env")
        sys.exit(1)

    # Build prompt
    goals = _read_business_goals()
    prompt = _build_prompt(goals, type_key)

    if args.dry:
        print(f"\n=== DRY RUN -- PROMPT PREVIEW ({type_key}) ===")
        print(prompt)
        print("=================================\n")
        return

    # Generate post
    logger.info("Calling AI to generate post...")
    post_text = _call_ai(prompt, api_key)

    char_count = len(post_text)
    logger.info("Post generated (%d chars)", char_count)
    if char_count > 1300:
        logger.warning("Post is %d chars -- over 1300 limit. Review before posting.", char_count)

    # Save and route
    draft_path, pending_path = _save_draft(post_text, type_key)
    logger.info("Draft saved:   %s", draft_path)
    logger.info("Pending:       %s", pending_path)

    _update_dashboard(draft_path.name)

    print(f"\n--- LinkedIn {type_key} post draft generated ---")
    print(f"  Draft:   {draft_path}")
    print(f"  Pending: {pending_path}")
    print(f"  Chars:   {char_count}/1300")
    print("\nReview in Obsidian then run: /approval-handler")
    print("-------------------------------------\n")


if __name__ == "__main__":
    main()
