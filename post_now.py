"""
post_now.py — Silver Tier One-Command LinkedIn Poster

Ek command mein:
  1. AI se post generate karta hai (Ollama ya Claude API)
  2. Terminal mein dikhata hai
  3. Aap approve karte ho (y/n)
  4. Browser khulta hai — aap sirf "Post" click karo

Usage:
    python post_now.py                   # personal post
    python post_now.py --type company    # company page post
    python post_now.py --dry             # sirf preview, koi action nahi
"""

import os
import sys
import io
import argparse
import logging
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PostNow")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT   = Path("silver_tier")
PENDING = VAULT / "Pending_Approval"
APPROVED = VAULT / "Approved"
DONE    = VAULT / "Done"
LI_DRAFTS = VAULT / "LinkedIn_Drafts"
BUSINESS_GOALS = VAULT / "Business_Goals.md"
APPROVAL_LOG   = VAULT / "Approval_Log.md"

MODEL      = "claude-haiku-4-5-20251001"
MAX_TOKENS = 800

POST_TYPES = {
    "personal": {
        "prefix":  "LI_PERSONAL_",
        "voice":   "personal (use 'I', 'my', first-person founder voice)",
        "script":  "linkedin_personal_mcp.py",
        "label":   "Personal Profile",
    },
    "company": {
        "prefix":  "LI_CO_",
        "voice":   "company (use 'we', 'our clients', company voice)",
        "script":  "linkedin_company_mcp.py",
        "label":   "Company Page",
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_env():
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    return key


def _read_business_goals() -> str:
    if BUSINESS_GOALS.exists():
        return BUSINESS_GOALS.read_text(encoding="utf-8")
    return "Focus: AI automation for founders. Audience: solopreneurs."


def _build_prompt(goals_text: str, type_key: str) -> str:
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
    """Call OpenRouter API (OpenAI-compatible, free models available)."""
    import urllib.request, json, time
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    if not model:
        model = os.environ.get("OPENROUTER_MODEL", OPENROUTER_MODELS_FALLBACK[0])

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800,
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
    """Try multiple OpenRouter models until one works."""
    import time
    primary = os.environ.get("OPENROUTER_MODEL", OPENROUTER_MODELS_FALLBACK[0])
    models  = [primary] + [m for m in OPENROUTER_MODELS_FALLBACK if m != primary]
    for model in models:
        try:
            logger.info("OpenRouter: trying %s...", model)
            result = _call_openrouter(prompt, model)
            logger.info("OpenRouter success with %s", model)
            return result
        except Exception as e:
            logger.warning("OpenRouter %s failed: %s", model, e)
            time.sleep(2)
    raise RuntimeError("All OpenRouter models failed.")


def _call_ollama(prompt: str) -> str:
    import urllib.request, json
    payload = json.dumps({
        "model": "llama3.2",
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["response"].strip()


STATIC_POSTS = {
    "personal": [
        """Most founders waste 3 hours a day on tasks an AI could do in 3 minutes.

I'm not talking about writing emails. I mean the boring stuff — sorting inquiries, scheduling follow-ups, drafting proposals.

I built a system that watches my Gmail, WhatsApp, and LinkedIn 24/7. When something needs a response, it drafts one and asks me to approve.

My job went from "doing" to "deciding."

If you're still manually managing your inbox in 2026, we need to talk.

What's the one task you wish someone else handled for you? Drop it in the comments.

#AIAutomation #FounderProductivity #Solopreneur""",
        """I saved 10 hours last week without hiring anyone.

Here's the system I use:
→ Gmail watcher flags urgent emails and drafts replies
→ WhatsApp messages get summarized and routed for approval
→ LinkedIn posts are generated and scheduled automatically

Total cost: ~$50/month in tools. Zero new hires.

The ROI isn't just time — it's mental clarity. When your AI handles the noise, you focus on the signal.

Want to know exactly how it's built? DM me "SYSTEM" and I'll send the breakdown.

#AIAutomation #DigitalFTE #Automation""",
    ],
    "company": [
        """We help founders get 10+ hours back every week — without hiring.

Our AI automation systems handle:
✓ Email triage and reply drafting
✓ WhatsApp message routing
✓ LinkedIn content scheduling
✓ Client follow-up reminders

One client went from 4-hour admin days to 45 minutes. Same output. Less stress.

If your team is doing work that should be automated, let's talk.

📩 DM us or comment "AUTOMATE" below.

#AIAutomation #BusinessAutomation #DigitalTransformation""",
        """The future of small business isn't more staff — it's smarter systems.

At our company, we've seen solo founders operate like teams of 5 using AI automation:
• Auto-drafted emails reviewed and sent in seconds
• Social media content planned and posted on schedule
• Client messages prioritized and responded to faster

The technology exists. The only question is when you'll use it.

Ready to build your AI employee? Let's connect.

#AIForBusiness #Automation #SmallBusiness""",
    ],
}

import random

def _static_fallback(type_key: str) -> str:
    posts = STATIC_POSTS.get(type_key, STATIC_POSTS["personal"])
    return random.choice(posts)


def _generate_post(prompt: str, api_key: str, type_key: str = "personal") -> str:
    # 1. OpenRouter (primary — free models, tries multiple on failure)
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        try:
            return _call_openrouter_with_fallback(prompt)
        except Exception as e:
            logger.warning("OpenRouter all models failed (%s) — trying Anthropic...", e)

    # 2. Anthropic (if credits available)
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
            msg = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            logger.info("Post generated via Claude API.")
            return msg.content[0].text.strip()
        except Exception as e:
            logger.warning("Claude API failed (%s) — trying Ollama...", e)

    # 3. Ollama (local)
    try:
        logger.info("Generating via Ollama (llama3.2)...")
        return _call_ollama(prompt)
    except Exception as e:
        logger.warning("Ollama bhi fail hua (%s) — static template use ho raha hai.", e)

    # 4. Static fallback
    logger.info("Static fallback post use ho rahi hai.")
    return _static_fallback(type_key)


def _slug(text: str) -> str:
    first = text.split("\n")[0][:50]
    s = "".join(c if c.isalnum() else "_" for c in first.lower()).strip("_")
    return s[:30] or "post"


def _save_draft(post_text: str, type_key: str) -> Path:
    """Save to LinkedIn_Drafts/ and Pending_Approval/ (for audit trail)."""
    for d in [LI_DRAFTS, PENDING, APPROVED, DONE]:
        d.mkdir(parents=True, exist_ok=True)

    prefix    = POST_TYPES[type_key]["prefix"]
    datestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename  = f"{prefix}{datestamp}_{_slug(post_text)}.md"
    char_count = len(post_text)

    content = f"""---
type: linkedin_post_{type_key}
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
status: approved
characters: {char_count}
---

{post_text}
"""
    # Save to Approved directly (human already approved in terminal)
    approved_path = APPROVED / filename
    approved_path.write_text(content, encoding="utf-8")

    # Also archive a copy to LinkedIn_Drafts for record
    draft_copy = LI_DRAFTS / filename
    draft_copy.write_text(content, encoding="utf-8")

    return approved_path


def _copy_to_clipboard(text: str) -> bool:
    """Copy text to Windows clipboard using PowerShell."""
    try:
        import subprocess
        # Write text to a temp file then Set-Clipboard from it
        tmp = Path("_clipboard_tmp.txt")
        tmp.write_text(text, encoding="utf-8")
        subprocess.run(
            ["powershell", "-Command", f"Get-Content '{tmp}' -Raw | Set-Clipboard"],
            check=True, capture_output=True, timeout=10
        )
        tmp.unlink(missing_ok=True)
        return True
    except Exception as e:
        logger.warning("Clipboard copy failed: %s", e)
        return False


def _post_via_api(post_text: str, dry: bool) -> bool:
    """Post via LinkedIn API if token exists, else return False."""
    token_file = Path(".linkedin_token.json")
    if not token_file.exists():
        return False
    try:
        import json as _json, urllib.request as _req
        token_data   = _json.loads(token_file.read_text(encoding="utf-8"))
        access_token = token_data["access_token"]
        member_id    = token_data.get("member_id", "")

        if not member_id:
            info_req = _req.Request(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            with _req.urlopen(info_req, timeout=15) as r:
                member_id = _json.loads(r.read()).get("sub", "")
            token_data["member_id"] = member_id
            token_file.write_text(_json.dumps(token_data, indent=2), encoding="utf-8")

        if dry:
            print("\n[DRY] Would post via LinkedIn API.")
            return True

        payload = _json.dumps({
            "author": f"urn:li:person:{member_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": post_text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }).encode("utf-8")

        api_req = _req.Request(
            "https://api.linkedin.com/v2/ugcPosts",
            data=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
        )
        with _req.urlopen(api_req, timeout=30) as r:
            post_id = r.headers.get("X-RestLi-Id", "unknown")

        print(f"\n[OK] LinkedIn API se post ho gayi! Post ID: {post_id}")
        return True
    except Exception as e:
        logger.warning("LinkedIn API post failed: %s", e)
        return False


def _open_browser(filepath: Path, type_key: str, dry: bool):
    """Post via API if available, else clipboard + browser fallback."""
    import webbrowser, shutil

    # Read post text
    raw = filepath.read_text(encoding="utf-8")
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        post_text = parts[2].strip() if len(parts) >= 3 else raw
    else:
        post_text = raw

    if dry:
        print("\n[DRY] Would post to LinkedIn.")
        return

    # Try API first
    if _post_via_api(post_text, dry=False):
        # Archive to Done
        dest = DONE / filepath.name
        DONE.mkdir(parents=True, exist_ok=True)
        if filepath.exists():
            shutil.move(str(filepath), str(dest))
        return

    # Fallback: clipboard + browser
    copied = _copy_to_clipboard(post_text)

    print("\n" + "=" * 55)
    print("  LinkedIn API token nahi mila — manual method:")
    if copied:
        print("  POST CLIPBOARD MEIN COPY HO GAYI!")
    print("=" * 55)

    webbrowser.open("https://www.linkedin.com/feed/")

    print("""
STEPS:
  1. LinkedIn feed mein "Start a post" click karo
  2. Ctrl+V dabao (post clipboard mein hai)
  3. "Post" button click karo
""")
    if not copied:
        print("--- POST TEXT (manually copy karo) ---")
        print(post_text)
        print("--- END ---")

    # Archive to Done
    dest = DONE / filepath.name
    DONE.mkdir(parents=True, exist_ok=True)
    if filepath.exists():
        shutil.move(str(filepath), str(dest))

    # Log
    if APPROVAL_LOG.exists():
        with APPROVAL_LOG.open("a", encoding="utf-8") as lf:
            lf.write(
                f"| {datetime.now().strftime('%Y-%m-%d %H:%M')} "
                f"| {filepath.name} | post_now | {type_key} | manual |\n"
            )


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    _load_env()

    parser = argparse.ArgumentParser(description="Silver Tier — One-Command LinkedIn Post")
    parser.add_argument("--type", choices=["personal", "company"], default="personal",
                        help="Post type: personal (default) or company")
    parser.add_argument("--dry", action="store_true",
                        help="Preview only — no browser, no files saved")
    args = parser.parse_args()

    type_key = args.type
    label    = POST_TYPES[type_key]["label"]

    print(f"\n{'='*55}")
    print(f"  Silver Tier LinkedIn Post — {label}")
    print(f"{'='*55}\n")

    # Step 1: Generate post
    print("Step 1/3: AI se post generate ho rahi hai...")
    api_key = _load_api_key()
    goals   = _read_business_goals()
    prompt  = _build_prompt(goals, type_key)

    post_text = _generate_post(prompt, api_key, type_key)

    char_count = len(post_text)

    # Step 2: Show and ask for approval
    print(f"\nStep 2/3: Post review karo ({char_count}/1300 chars)\n")
    print("-" * 55)
    print(post_text)
    print("-" * 55)

    if char_count > 1300:
        print(f"\n[WARN] Post {char_count} chars hai — 1300 se zyada. LinkedIn truncate kar sakta hai.")

    if args.dry:
        print("\n[DRY RUN] Koi action nahi liya.")
        return

    print("\nApprove karo? (y = haan, post karo | n = cancel | e = edit karni hai)")
    choice = input(">>> ").strip().lower()

    if choice == "n":
        print("Cancel. Koi post nahi ki gayi.")
        return
    elif choice == "e":
        print("\nPost text copy karo, edit karo, phir manually chalao:")
        print(f"  python linkedin_{type_key}_mcp.py --post <filename>")
        # Still save to Pending_Approval for manual review
        pending_path = PENDING / f"{POST_TYPES[type_key]['prefix']}{datetime.now().strftime('%Y%m%d_%H%M')}_draft.md"
        pending_path.write_text(f"---\ntype: linkedin_post_{type_key}\nstatus: draft\n---\n\n{post_text}\n", encoding="utf-8")
        print(f"Draft saved: {pending_path}")
        return
    elif choice != "y":
        print("Invalid input. Cancel.")
        return

    # Step 3: Save and open browser
    print("\nStep 3/3: Browser mein LinkedIn khul raha hai...")
    approved_path = _save_draft(post_text, type_key)
    _open_browser(approved_path, type_key, dry=False)


if __name__ == "__main__":
    main()
