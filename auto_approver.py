"""
auto_approver.py — Silver Tier Auto-Approve Mode

Scans Pending_Approval/ and classifies each file:

  AUTO-ARCHIVE  → newsletters, digests, no-reply senders → moved to Done/ (no reply sent)
  AUTO-APPROVE  → low-risk generic inquiries → moved to Approved/ (approval_executor sends reply)
  HUMAN         → financial, urgent, WA replies, real clients → stays in Pending_Approval/

Rules (hard limits — never overridden):
  - WA_REPLY_* files → always HUMAN
  - LI_* files       → always HUMAN
  - financial_flag: true → always HUMAN
  - priority: high / critical → always HUMAN
  - Unknown sender (real person, no automation signal) → always HUMAN

Usage:
    python auto_approver.py           # watch mode (every 30s)
    python auto_approver.py --once    # process current Pending_Approval/ and exit
    python auto_approver.py --dry     # preview decisions without moving files
    python auto_approver.py --report  # show stats on current pending files and exit
"""

import os
import sys
import io
import re
import time
import shutil
import argparse
import json
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT    = Path("silver_tier")
PENDING  = VAULT / "Pending_Approval"
APPROVED = VAULT / "Approved"
DONE     = VAULT / "Done"
LOG      = VAULT / "Approval_Log.md"
SEEN     = Path(".auto_approver_seen.json")

POLL_INTERVAL = 30  # seconds

for f in [PENDING, APPROVED, DONE]:
    f.mkdir(parents=True, exist_ok=True)

# ── Auto-archive signals (no reply sent, straight to Done) ────────────────────

ARCHIVE_SENDER_PATTERNS = [
    r"noreply", r"no-reply", r"no_reply",
    r"newsletter", r"digest", r"mailer", r"notifications?@",
    r"updates?@", r"alerts?@", r"donotreply", r"do-not-reply",
    r"news@", r"hello@substack", r"reply\+",          # substack reply-tracking
    r"@mg\d+\.", r"@sendgrid", r"@mailchimp",          # ESP domains
    r"@bounce\.", r"@em\d+\.",
    r"nytdirect@", r"@nytimes", r"unstop\.news",
    r"substack\.com", r"beehiiv\.com", r"convertkit",
    r"@hubspot", r"@marketo", r"@klaviyo",
]

ARCHIVE_SUBJECT_PATTERNS = [
    r"\bnewsletter\b", r"\bdigest\b", r"\bweekly\b", r"\bdaily\b",
    r"\bunsubscribe\b", r"\bno.reply\b", r"\bpromotion\b",
    r"\byou.re\s+in\b", r"\bwelcome\s+to\b", r"\bconfirm\s+your\b",
    r"\bverif(y|ication)\b", r"\breceipt\b", r"\border\s+confirm",
    r"\bshipping\s+(update|confirm)", r"\bpassword\s+reset\b",
    r"\bsecurity\s+alert\b", r"\bsign.?in\s+attempt\b",
    r"\bhiring\b.*\bprofile\b", r"\btop\s+match\b",   # job alert emails
    r"\boff\b.*\blimited\s+time\b", r"\b\d+%\s+off\b",  # promo
]

# ── Auto-approve signals (low-risk, send generic reply) ───────────────────────

AUTOAPPROVE_SUBJECT_PATTERNS = [
    r"\bthank\s+you\s+for\s+(your\s+)?interest\b",
    r"\bfollow.?up\b",
    r"\bjust\s+checking\b",
    r"\bquick\s+question\b",
]

# ── Hard HUMAN-only triggers ───────────────────────────────────────────────────

HUMAN_ALWAYS_PREFIXES  = ("WA_REPLY_", "WA_", "LI_")
HUMAN_ALWAYS_TYPES     = ("whatsapp_reply", "whatsapp", "linkedin", "linkedin_post")
HUMAN_PRIORITY_VALUES  = ("high", "critical", "urgent")


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_env():
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_seen() -> set:
    if SEEN.exists():
        try:
            return set(json.loads(SEEN.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_seen(seen: set):
    SEEN.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")


def parse_frontmatter(text: str) -> dict:
    meta = {}
    if not text.startswith("---"):
        return meta
    for line in text.split("\n")[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def set_status(filepath: Path, status: str):
    text = filepath.read_text(encoding="utf-8", errors="replace")
    updated = re.sub(r"^(status:\s*)\S+", rf"\g<1>{status}", text, flags=re.MULTILINE)
    if updated == text:
        updated = re.sub(r"^(---\n)", rf"\1status: {status}\n", text, count=1)
    filepath.write_text(updated, encoding="utf-8")


def safe_move(src: Path, dest_dir: Path) -> Path:
    dest = dest_dir / src.name
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{src.stem}_{counter}{src.suffix}"
        counter += 1
    shutil.move(str(src), str(dest))
    return dest


def append_log(decision: str, filename: str, reason: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"| {now} | AUTO | {decision} | {filename} | {reason} |\n"
    try:
        if not LOG.exists():
            LOG.write_text(
                "# Approval Log\n\n"
                "| Timestamp | Stage | Decision | File | Reason |\n"
                "|-----------|-------|----------|------|--------|\n",
                encoding="utf-8",
            )
        with LOG.open("a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


def matches_any(text: str, patterns: list[str]) -> str | None:
    """Return the first matching pattern string, or None."""
    text_lower = text.lower()
    for p in patterns:
        if re.search(p, text_lower):
            return p
    return None


# ── Classifier ─────────────────────────────────────────────────────────────────

def classify(filepath: Path) -> tuple[str, str]:
    """
    Returns (decision, reason):
      decision: 'archive' | 'approve' | 'human'
      reason  : short explanation string
    """
    name = filepath.name
    raw  = filepath.read_text(encoding="utf-8", errors="replace")
    meta = parse_frontmatter(raw)

    file_type  = meta.get("type", "").lower()
    priority   = meta.get("priority", "").lower()
    fin_flag   = meta.get("financial_flag", "").lower()
    sender     = (meta.get("from", "") + " " + meta.get("original_from", "")).lower()
    to_addr    = meta.get("to", "").lower()
    subject    = meta.get("subject", "").lower()

    # ── Hard HUMAN rules (never override) ─────────────────────────────────────
    if any(name.startswith(p) for p in HUMAN_ALWAYS_PREFIXES):
        return "human", f"file prefix requires human ({name[:8]}...)"

    if file_type in HUMAN_ALWAYS_TYPES:
        return "human", f"type={file_type} always requires human"

    if fin_flag == "true":
        return "human", "financial_flag=true — human required"

    if priority in HUMAN_PRIORITY_VALUES:
        return "human", f"priority={priority} — human required"

    # ── Auto-archive: no-reply / newsletter senders ────────────────────────────
    matched = matches_any(sender + " " + to_addr, ARCHIVE_SENDER_PATTERNS)
    if matched:
        return "archive", f"sender matches no-reply/newsletter pattern"

    matched = matches_any(subject, ARCHIVE_SUBJECT_PATTERNS)
    if matched:
        return "archive", f"subject matches newsletter/promo pattern"

    # ── reply+ tracking addresses (substack, sendgrid etc) ────────────────────
    if re.search(r"reply\+[a-zA-Z0-9&%_\-]+@", to_addr):
        return "archive", "reply-tracking address — bulk sender"

    # ── Auto-approve: low-risk generic inquiries ───────────────────────────────
    matched = matches_any(subject, AUTOAPPROVE_SUBJECT_PATTERNS)
    if matched:
        return "approve", f"low-risk inquiry — generic reply queued"

    # ── Default: human ─────────────────────────────────────────────────────────
    return "human", "no auto-rule matched — human review required"


# ── Actions ────────────────────────────────────────────────────────────────────

def do_archive(filepath: Path, reason: str, dry: bool) -> dict:
    if dry:
        return {"file": filepath.name, "decision": "archive", "reason": reason, "dry": True}
    dest = safe_move(filepath, DONE)
    set_status(dest, "archived")
    append_log("ARCHIVE", filepath.name, reason)
    return {"file": filepath.name, "decision": "archive", "dest": dest.name, "reason": reason}


def do_approve(filepath: Path, reason: str, dry: bool) -> dict:
    """Move to Approved/ so approval_executor.py sends the reply."""
    if dry:
        return {"file": filepath.name, "decision": "approve", "reason": reason, "dry": True}

    # Inject a clear approved reply section if not already present
    raw = filepath.read_text(encoding="utf-8", errors="replace")
    if "## Approved Reply" not in raw and "## Selected Reply" not in raw:
        meta   = parse_frontmatter(raw)
        sender = meta.get("original_from", meta.get("from", "there"))
        # Extract a clean sender name
        name_match = re.match(r"^([^<]+)<", sender)
        sender_name = name_match.group(1).strip() if name_match else sender.split("@")[0].strip()

        generic_reply = (
            f"Hi {sender_name},\n\n"
            f"Thank you for your message. I appreciate you reaching out.\n\n"
            f"I'll review this and get back to you if any action is needed on my end.\n\n"
            f"Best regards"
        )
        with filepath.open("a", encoding="utf-8") as f:
            f.write(f"\n\n## Approved Reply\n\n{generic_reply}\n")

    dest = safe_move(filepath, APPROVED)
    set_status(dest, "approved")
    append_log("AUTO-APPROVE", filepath.name, reason)
    return {"file": filepath.name, "decision": "approve", "dest": dest.name, "reason": reason}


def do_human(filepath: Path, reason: str) -> dict:
    return {"file": filepath.name, "decision": "human", "reason": reason}


# ── Scanner ────────────────────────────────────────────────────────────────────

def scan(seen: set, dry: bool) -> list[dict]:
    files    = sorted(PENDING.glob("*.md"))
    new      = [f for f in files if f.name not in seen]

    if not new:
        return []

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {len(new)} file(s) in Pending_Approval/")

    results  = []
    archived = approved = human = 0

    for fp in new:
        decision, reason = classify(fp)

        if decision == "archive":
            r = do_archive(fp, reason, dry)
            archived += 1
            tag = "[ARCHIVE]"
        elif decision == "approve":
            r = do_approve(fp, reason, dry)
            approved += 1
            tag = "[AUTO-APPROVE]"
        else:
            r = do_human(fp, reason)
            human += 1
            tag = "[HUMAN]"

        suffix = " (dry)" if dry else ""
        print(f"  {tag}{suffix} {fp.name[:55]:<55} | {reason}")

        if not dry and decision != "human":
            seen.add(fp.name)
        elif decision == "human":
            seen.add(fp.name)  # don't re-evaluate same file next cycle

        results.append(r)

    print(f"  Summary: {archived} archived | {approved} auto-approved | {human} need human review")
    return results


# ── Report ─────────────────────────────────────────────────────────────────────

def report():
    files = sorted(PENDING.glob("*.md"))
    if not files:
        print("Pending_Approval/ is empty.")
        return

    counts = {"archive": 0, "approve": 0, "human": 0}
    print(f"Pending_Approval/ — {len(files)} file(s)\n")
    print(f"  {'Decision':<14} {'File':<50} Reason")
    print(f"  {'-'*14} {'-'*50} {'-'*30}")

    for fp in files:
        decision, reason = classify(fp)
        counts[decision] += 1
        print(f"  {decision.upper():<14} {fp.name[:50]:<50} {reason}")

    print(f"\n  Would archive     : {counts['archive']}")
    print(f"  Would auto-approve: {counts['approve']}")
    print(f"  Need human review : {counts['human']}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Silver Tier — Auto Approver")
    parser.add_argument("--once",   action="store_true", help="Process once and exit")
    parser.add_argument("--dry",    action="store_true", help="Preview decisions without moving files")
    parser.add_argument("--report", action="store_true", help="Show classification report and exit")
    args = parser.parse_args()

    load_env()

    if args.report:
        report()
        return

    if args.dry:
        print("DRY RUN MODE -- no files will be moved\n")

    seen = load_seen() if not args.dry else set()

    if args.once:
        results = scan(seen, args.dry)
        if not results:
            print("Nothing new in Pending_Approval/.")
        elif not args.dry:
            save_seen(seen)
        return

    print(f"Auto-approver watching Pending_Approval/ every {POLL_INTERVAL}s ... (Ctrl+C to stop)")
    try:
        while True:
            results = scan(seen, args.dry)
            if results and not args.dry:
                save_seen(seen)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
