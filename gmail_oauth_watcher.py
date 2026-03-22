"""
gmail_oauth_watcher.py -- Gmail watcher using Google OAuth API (credentials.json)

First run: browser opens for Google login → token.json saved automatically.
Next runs: uses saved token.json (no browser needed).

Usage:
    python gmail_oauth_watcher.py          # continuous polling every 3 min
    python gmail_oauth_watcher.py --once   # check once and exit

Requirements:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
"""

import os
import sys
import io
import time
import base64
import logging
import argparse
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("GmailOAuth")

# ── Config ────────────────────────────────────────────────────────────────────

CREDENTIALS_FILE = Path("credentials.json")
TOKEN_FILE       = Path("token.json")
VAULT            = Path("silver_tier")
NEEDS_ACTION     = VAULT / "Needs_Action"
CHECK_INTERVAL   = 180  # 3 minutes

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_gmail_service():
    """Authenticate and return Gmail API service. Opens browser on first run."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.info("Token refreshed.")
        else:
            logger.info("Opening browser for Google login...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
            logger.info("Login successful!")

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        logger.info("Token saved to %s", TOKEN_FILE)

    return build("gmail", "v1", credentials=creds)


# ── Email processing ──────────────────────────────────────────────────────────

def get_email_body(service, msg_id: str) -> str:
    """Fetch full email body."""
    try:
        msg = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

        payload = msg.get("payload", {})
        parts = payload.get("parts", [])

        # Try plain text first
        for part in parts:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")[:2000]

        # Fallback: single part body
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")[:2000]

        return "(no body)"
    except Exception as e:
        return f"(error reading body: {e})"


def get_header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def classify_priority(subject: str, sender: str) -> str:
    urgent = {"urgent", "asap", "invoice", "payment", "due", "important",
              "overdue", "deadline", "follow up", "action required"}
    text = (subject + " " + sender).lower()
    return "high" if any(w in text for w in urgent) else "normal"


def check_emails(service, seen_ids: set) -> tuple[int, set]:
    """Check unread emails, create action files. Returns (count, updated_seen_ids)."""
    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)

    try:
        results = service.users().messages().list(
            userId="me", labelIds=["UNREAD", "INBOX"], maxResults=20
        ).execute()
    except Exception as e:
        logger.error("Gmail API error: %s", e)
        return 0, seen_ids

    messages = results.get("messages", [])
    new_count = 0

    for m in messages:
        msg_id = m["id"]
        if msg_id in seen_ids:
            continue

        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()

            headers  = msg.get("payload", {}).get("headers", [])
            subject  = get_header(headers, "Subject") or "(no subject)"
            sender   = get_header(headers, "From") or "Unknown"
            date_str = get_header(headers, "Date") or ""
            priority = classify_priority(subject, sender)

            body = get_email_body(service, msg_id)

            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"EMAIL_{ts}_{msg_id[:8]}.md"
            filepath = NEEDS_ACTION / filename

            filepath.write_text(f"""---
type: email
from: {sender}
subject: {subject}
received: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
date_header: {date_str}
priority: {priority}
status: pending
uid: {msg_id}
---

## Email Content

**From:** {sender}
**Subject:** {subject}
**Date:** {date_str}

### Body (preview)

{body}

---

## Suggested Actions
- [ ] Reply
- [ ] Archive
- [ ] Escalate
""", encoding="utf-8")

            seen_ids.add(msg_id)
            new_count += 1
            logger.info("New email: %s [%s] -- %s", filename, priority, subject[:60])

        except Exception as e:
            logger.error("Error processing message %s: %s", msg_id, e)

    return new_count, seen_ids


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gmail OAuth Watcher")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    args = parser.parse_args()

    if not CREDENTIALS_FILE.exists():
        logger.error("credentials.json not found in %s", Path.cwd())
        sys.exit(1)

    try:
        service = get_gmail_service()
    except Exception as e:
        logger.error("Auth failed: %s", e)
        sys.exit(1)

    seen_ids = set()

    if args.once:
        count, _ = check_emails(service, seen_ids)
        logger.info("Done. %d new email(s) processed.", count)
        return

    logger.info("Gmail OAuth Watcher started (polling every %ds)", CHECK_INTERVAL)

    while True:
        count, seen_ids = check_emails(service, seen_ids)
        if count:
            logger.info("%d new email(s) written to Needs_Action/", count)

        try:
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Stopped.")
            break


if __name__ == "__main__":
    main()
