"""
gmail_watcher.py -- Silver Tier Gmail monitor (IMAP-based, no Google API needed)

Polls Gmail every 3 minutes for unread emails via IMAP SSL.
Creates EMAIL_*.md files in Needs_Action/ for workflow_runner to process.

Setup:
  1. Enable 2-Step Verification on your Google account.
  2. Create an App Password at: https://myaccount.google.com/apppasswords
  3. Add to your .env file:
       EMAIL_ADDRESS=you@gmail.com
       EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

Usage:
    python gmail_watcher.py                    # default vault: silver_tier
    python gmail_watcher.py --vault silver_tier
    python gmail_watcher.py --once             # single check and exit
"""

import os
import sys
import io
import time
import email
import email.message
import imaplib
import json
import argparse
import logging
from email.header import decode_header
from pathlib import Path
from datetime import datetime

# Fix Windows cp1252 encoding issues
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("GmailWatcher")

# ── Config ────────────────────────────────────────────────────────────────────

IMAP_SERVER    = "imap.gmail.com"
IMAP_PORT      = 993
CHECK_INTERVAL = 180   # seconds between polls (3 minutes)
DEDUP_FILE     = ".gmail_seen_ids.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_env():
    """Load EMAIL_ADDRESS and EMAIL_APP_PASSWORD from env or .env file."""
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    address  = os.environ.get("EMAIL_ADDRESS", "")
    password = os.environ.get("EMAIL_APP_PASSWORD", "")
    return address, password


def _decode_header_value(raw) -> str:
    """Decode an email header value (handles encoded words)."""
    parts = decode_header(raw or "")
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result).strip()


def _get_body(msg: email.message.Message) -> str:
    """Extract plain-text body from email (falls back to HTML snippet)."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and not part.get("Content-Disposition"):
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")

    # Trim body to avoid giant files
    return body[:2000].strip()


def _load_seen(vault: Path) -> set:
    path = vault / DEDUP_FILE
    if path.exists():
        try:
            return set(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def _save_seen(vault: Path, seen: set):
    path = vault / DEDUP_FILE
    # Keep only the last 500 IDs to avoid unbounded growth
    ids = list(seen)[-500:]
    path.write_text(json.dumps(ids), encoding="utf-8")


def _classify_priority(subject: str, sender: str) -> str:
    """Simple heuristic: flag urgent keywords as high priority."""
    urgent_words = {"urgent", "asap", "invoice", "payment", "due", "important",
                    "overdue", "deadline", "follow up", "action required"}
    text = (subject + " " + sender).lower()
    if any(w in text for w in urgent_words):
        return "high"
    return "normal"


# ── Core watcher ─────────────────────────────────────────────────────────────

class GmailWatcher:
    def __init__(self, vault_path: Path, address: str, password: str):
        self.vault      = vault_path
        self.address    = address
        self.password   = password
        self.needs_action = vault_path / "Needs_Action"
        self.needs_action.mkdir(parents=True, exist_ok=True)
        self.seen       = _load_seen(vault_path)

    def connect(self) -> imaplib.IMAP4_SSL:
        """Open an IMAP SSL connection and login."""
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(self.address, self.password)
        return mail

    def check_once(self) -> int:
        """Fetch unread emails and create action files. Returns count of new items."""
        try:
            mail = self.connect()
        except imaplib.IMAP4.error as e:
            logger.error("IMAP login failed: %s", e)
            logger.error("Check EMAIL_ADDRESS / EMAIL_APP_PASSWORD in your .env file.")
            return 0

        try:
            mail.select("INBOX")
            # Search for unseen emails (IMAP standard)
            status, data = mail.search(None, "UNSEEN")
            if status != "OK":
                return 0

            ids = data[0].split()
            new_count = 0

            for eid in ids:
                uid = eid.decode()
                if uid in self.seen:
                    continue

                _, msg_data = mail.fetch(eid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subject  = _decode_header_value(msg.get("Subject", "(no subject)"))
                sender   = _decode_header_value(msg.get("From", "Unknown"))
                date_str = msg.get("Date", "")
                body     = _get_body(msg)
                priority = _classify_priority(subject, sender)

                # Create action file
                safe_subject = "".join(
                    c if c.isalnum() or c in " _-" else "_" for c in subject
                )[:40].strip("_")
                ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"EMAIL_{ts}_{uid}.md"
                filepath = self.needs_action / filename

                filepath.write_text(f"""---
type: email
from: {sender}
subject: {subject}
received: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
date_header: {date_str}
priority: {priority}
status: pending
uid: {uid}
---

## Email Content

**From:** {sender}
**Subject:** {subject}
**Date:** {date_str}

### Body (preview)

{body or "(no body)"}

---

## Suggested Actions
- [ ] Reply
- [ ] Archive
- [ ] Escalate
""", encoding="utf-8")

                self.seen.add(uid)
                new_count += 1
                logger.info("New email saved: %s [%s] -- %s", filename, priority, subject[:60])

            _save_seen(self.vault, self.seen)
            mail.logout()
            return new_count

        except Exception as e:
            logger.error("Error checking emails: %s", e)
            try:
                mail.logout()
            except Exception:
                pass
            return 0

    def run(self):
        """Poll Gmail continuously until Ctrl+C."""
        logger.info("Gmail Watcher started (polling every %ds)", CHECK_INTERVAL)
        logger.info("Watching inbox for: %s", self.address)
        logger.info("Action files -> %s", self.needs_action.resolve())

        while True:
            count = self.check_once()
            if count:
                logger.info("%d new email(s) written to Needs_Action/", count)
            else:
                logger.debug("No new emails.")

            try:
                time.sleep(CHECK_INTERVAL)
            except KeyboardInterrupt:
                logger.info("Gmail Watcher stopped.")
                break


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Silver Tier -- Gmail Watcher (IMAP)")
    parser.add_argument("--vault", default="silver_tier",
                        help="Path to Obsidian vault (default: silver_tier/)")
    parser.add_argument("--once", action="store_true",
                        help="Check once and exit (no loop)")
    args = parser.parse_args()

    vault = Path(args.vault)

    _load_env()
    address  = os.environ.get("EMAIL_ADDRESS", "")
    password = os.environ.get("EMAIL_APP_PASSWORD", "")

    if not address or not password:
        logger.error("Missing credentials. Add to your .env file:")
        logger.error("  EMAIL_ADDRESS=you@gmail.com")
        logger.error("  EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx")
        logger.error("  (Get an App Password at: https://myaccount.google.com/apppasswords)")
        sys.exit(1)

    watcher = GmailWatcher(vault_path=vault, address=address, password=password)

    if args.once:
        count = watcher.check_once()
        logger.info("Done. %d new email(s) processed.", count)
    else:
        watcher.run()


if __name__ == "__main__":
    main()
