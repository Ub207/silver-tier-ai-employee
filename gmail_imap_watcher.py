import time
import imaplib
import smtplib
import email
import json
import re
import sys
import io
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import logging
import anthropic

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GmailIMAPWatcher")

VAULT_PATH = Path("D:/silver_tier/silver_tier")
NEEDS_ACTION    = VAULT_PATH / "Needs_Action"
PENDING_APPROVAL = VAULT_PATH / "Pending_Approval"
DONE            = VAULT_PATH / "Done"
for folder in [NEEDS_ACTION, PENDING_APPROVAL, DONE]:
    folder.mkdir(exist_ok=True)

SEEN_IDS_FILE = Path("D:/silver_tier/.gmail_seen_ids.json")

GMAIL_EMAIL  = "usmanubaidurrehman@gmail.com"
APP_PASSWORD = "hnwf xvho ugtd ouay"

# ─── Helpers ────────────────────────────────────────────────────────────────

def load_seen_ids():
    if SEEN_IDS_FILE.exists():
        return set(json.loads(SEEN_IDS_FILE.read_text(encoding="utf-8")))
    return set()

def save_seen_ids(seen_ids):
    SEEN_IDS_FILE.write_text(json.dumps(list(seen_ids)), encoding="utf-8")

SKIP_SENDERS = [
    "mailer-daemon", "noreply", "no-reply", "donotreply",
    "notifications@", "newsletter", "newsletters@",
    "mail delivery", "postmaster", "bounce", "auto-reply",
    "support@", "info@", "hello@", "team@"
]

def extract_email_address(raw):
    match = re.search(r'<(.+?)>', raw)
    return match.group(1) if match else raw.strip()

def is_system_email(from_, subject):
    from_lower = from_.lower()
    subject_lower = subject.lower()
    if any(skip in from_lower for skip in SKIP_SENDERS):
        return True
    if any(skip in subject_lower for skip in ["unsubscribe", "delivery status", "delivery failure", "out of office", "auto-reply"]):
        return True
    return False

# ─── B: AI Reply Draft ──────────────────────────────────────────────────────

def generate_ai_reply(subject, from_, body):
    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": (
                    f"Write a short, professional email reply.\n\n"
                    f"From: {from_}\nSubject: {subject}\n\nEmail:\n{body[:500]}\n\n"
                    "Just write the reply body. No subject line. No 'Subject:' prefix."
                )
            }]
        )
        return msg.content[0].text.strip()
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "Thank you for your email. I will get back to you shortly."

# ─── C: Auto-Send Approved Replies ──────────────────────────────────────────

def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"]    = GMAIL_EMAIL
        msg["To"]      = to_email
        msg["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_EMAIL, APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"SMTP error: {e}")
        return False

def check_and_send_approved():
    for reply_file in PENDING_APPROVAL.glob("REPLY_EMAIL_*.md"):
        content = reply_file.read_text(encoding="utf-8")
        if "status: approved" not in content:
            continue

        to_email = subject = ""
        for line in content.splitlines():
            if line.startswith("to: "):
                to_email = line[4:].strip()
            elif line.startswith("subject: "):
                subject = line[9:].strip()

        reply_body = ""
        if "## Reply Draft" in content:
            reply_body = content.split("## Reply Draft")[1].strip()
            if "## Instructions" in reply_body:
                reply_body = reply_body.split("## Instructions")[0].strip()

        if not (to_email and subject and reply_body):
            logger.warning(f"Incomplete reply file: {reply_file.name}")
            continue

        logger.info(f"Sending approved reply to {to_email} ...")
        if send_email(to_email, subject, reply_body):
            sent_content = content.replace("status: approved", "status: sent")
            done_path = DONE / reply_file.name
            done_path.write_text(sent_content, encoding="utf-8")
            reply_file.unlink()
            logger.info(f"Sent + moved to Done: {reply_file.name}")

# ─── A: Fetch All Emails ─────────────────────────────────────────────────────

def fetch_all_emails():
    seen_ids  = load_seen_ids()
    new_count = 0

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_EMAIL, APP_PASSWORD)
        mail.select("inbox")

        _, data = mail.search(None, 'ALL')
        email_ids = data[0].split()

        for num in email_ids[-20:]:  # last 20 only
            email_id = num.decode()
            if email_id in seen_ids:
                continue

            _, msg_data = mail.fetch(num, "(RFC822)")
            raw_email   = msg_data[0][1]
            msg         = email.message_from_bytes(raw_email)

            subject = decode_header(msg["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode(errors="ignore")

            from_ = msg.get("From", "Unknown")
            date_ = msg.get("Date", "Unknown")
            to_email = extract_email_address(msg.get("Reply-To", from_))

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            body = body.encode("ascii", errors="ignore").decode("ascii")

            # Skip system/newsletter emails
            if is_system_email(from_, subject):
                logger.info(f"[SKIP] {subject} | {from_}")
                seen_ids.add(email_id)
                continue

            # Save original email to Needs_Action
            email_content = (
                f"---\ntype: email\nfrom: {from_}\nsubject: {subject}\n"
                f"date: {date_}\nreceived: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"status: pending\n---\n\n## Email Content\n{body[:800]}\n"
            )
            email_file = f"EMAIL_{email_id}_{int(time.time())}.md"
            (NEEDS_ACTION / email_file).write_text(email_content, encoding="utf-8")

            # Generate AI reply → save to Pending_Approval for review
            logger.info(f"Generating AI reply for: {subject}")
            ai_reply = generate_ai_reply(subject, from_, body)

            reply_content = (
                f"---\ntype: email_reply\nto: {to_email}\nsubject: {subject}\n"
                f"original_from: {from_}\nstatus: pending\n---\n\n"
                f"## Original Email\nFrom: {from_}\nSubject: {subject}\n\n"
                f"{body[:300]}\n\n"
                f"## AI Reply Draft\n{ai_reply}\n\n"
                f"## Action\n"
                f"Change status: pending  →  status: approved   to SEND\n"
                f"Change status: pending  →  status: rejected   to DISCARD\n"
            )
            reply_file = f"REPLY_EMAIL_{email_id}_{int(time.time())}.md"
            (PENDING_APPROVAL / reply_file).write_text(reply_content, encoding="utf-8")

            seen_ids.add(email_id)
            new_count += 1
            logger.info(f"[DRAFT READY] {subject} | From: {from_}")

        save_seen_ids(seen_ids)
        mail.logout()
        logger.info(f"{new_count} new email(s) processed." if new_count else "No new emails.")

    except Exception as e:
        logger.error(f"Error: {e}")

# ─── Main Loop ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Gmail Watcher Started (fetch + AI draft + auto-send)")
    while True:
        fetch_all_emails()
        check_and_send_approved()
        time.sleep(180)