"""
archive_stale_emails.py — One-time cleanup of stale email backlog

Moves EMAIL_*.md files from Needs_Action to Done/Archived_Emails/
if they are newsletters/promotional/notification emails that don't need replies.

Safe to run multiple times (skips already-moved files).
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

VAULT        = Path("D:/silver_tier/silver_tier")
NEEDS_ACTION = VAULT / "Needs_Action"
DONE         = VAULT / "Done"
ARCHIVE_DIR  = DONE / "Archived_Emails"
APPROVAL_LOG = VAULT / "Approval_Log.md"

# Keywords that indicate no-reply emails (newsletters, notifications, promos)
NO_REPLY_SENDERS = [
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "newsletter", "notifications", "updates", "mailer",
    "digest", "info@", "support@", "hello@", "team@",
    "news@", "alerts@", "marketing@", "promo",
]

NO_REPLY_SUBJECTS = [
    "unsubscribe", "newsletter", "digest", "your weekly",
    "reading month", "offer", "deal", "sale", "discount",
    "notification", "alert", "reminder", "confirm",
]


def is_no_reply_email(filepath: Path) -> bool:
    """Return True if the email is a newsletter/notification that needs no reply."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="ignore").lower()
        for kw in NO_REPLY_SENDERS:
            if kw in text[:500]:  # Check frontmatter area
                return True
        for kw in NO_REPLY_SUBJECTS:
            if kw in text[:500]:
                return True
    except Exception:
        pass
    return False


def main():
    if not NEEDS_ACTION.exists():
        print("Needs_Action folder not found.")
        return

    email_files = sorted(NEEDS_ACTION.glob("EMAIL_*.md"))
    if not email_files:
        print("No EMAIL files to archive.")
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    archived = 0
    kept = 0

    for f in email_files:
        if is_no_reply_email(f):
            dst = ARCHIVE_DIR / f.name
            if dst.exists():
                dst = ARCHIVE_DIR / f"{f.stem}_{datetime.now().strftime('%H%M%S%f')}.md"
            shutil.move(str(f), str(dst))
            archived += 1
        else:
            kept += 1

    # Log to Approval_Log
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = (
        f"\n## {ts} — Stale Email Archive\n"
        f"Archived {archived} newsletter/notification emails to Done/Archived_Emails/\n"
        f"Kept {kept} EMAIL files in Needs_Action for review.\n"
    )
    if APPROVAL_LOG.exists():
        with APPROVAL_LOG.open("a", encoding="utf-8") as lf:
            lf.write(log_entry)

    print(f"Done — archived {archived} no-reply emails, kept {kept} for review.")


if __name__ == "__main__":
    main()
