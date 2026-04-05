"""
send_email.py — Gmail Send skill
Sends a real email via Gmail SMTP (TLS, port 587).

Usage:
    python send_email.py --to <email> --subject <text> --body <text> [--cc <email>] [--html]

Environment variables required:
    EMAIL_ADDRESS    — your Gmail address
    EMAIL_PASSWORD   — Gmail App Password (not account password)
"""

import os
import sys
import io
import re
import argparse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


# ── Env loader ─────────────────────────────────────────────────────────────────

def load_env():
    """Load .env from project root (two levels up from scripts/)."""
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def validate_email(address: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", address.strip()))


# ── Core send function ─────────────────────────────────────────────────────────

def send_email(to: str, subject: str, body: str, cc: str = "", html: bool = False) -> None:
    sender   = os.environ.get("EMAIL_ADDRESS", "").strip()
    password = os.environ.get("EMAIL_PASSWORD", "").strip()

    if not sender:
        print("[ERROR] EMAIL_ADDRESS is not set. Add it to your .env file.")
        sys.exit(1)
    if not password:
        print("[ERROR] EMAIL_PASSWORD is not set. Add your Gmail App Password to .env.")
        sys.exit(1)
    if not validate_email(to):
        print(f"[ERROR] Invalid recipient address: {to}")
        sys.exit(1)

    recipients = [to.strip()]
    if cc:
        for addr in cc.split(","):
            addr = addr.strip()
            if addr:
                if not validate_email(addr):
                    print(f"[ERROR] Invalid CC address: {addr}")
                    sys.exit(1)
                recipients.append(addr)

    msg = MIMEMultipart("alternative")
    msg["From"]    = sender
    msg["To"]      = to.strip()
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type, "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[OK] Email sent to {to}")
        print(f"     Subject : {subject}")
        print(f"     From    : {sender}")
        if cc:
            print(f"     CC      : {cc}")
        print(f"     Sent at : {now}")

    except smtplib.SMTPAuthenticationError:
        print("[ERROR] Authentication failed.")
        print("        Check EMAIL_ADDRESS and EMAIL_PASSWORD in your .env file.")
        print("        Make sure you are using a Gmail App Password, not your account password.")
        sys.exit(1)
    except smtplib.SMTPRecipientsRefused as e:
        print(f"[ERROR] Recipient refused by server: {e}")
        sys.exit(1)
    except smtplib.SMTPException as e:
        print(f"[ERROR] SMTP error: {e}")
        sys.exit(1)
    except OSError as e:
        print(f"[ERROR] Network error: {e}")
        print(f"        Could not connect to {SMTP_HOST}:{SMTP_PORT}. Check your internet connection.")
        sys.exit(1)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gmail Send — Silver Tier AI Employee")
    parser.add_argument("--to",      required=True, help="Recipient email address")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--body",    required=True, help="Email body (plain text or HTML)")
    parser.add_argument("--cc",      default="",    help="CC address(es), comma-separated")
    parser.add_argument("--html",    action="store_true", help="Treat body as HTML")
    args = parser.parse_args()

    load_env()
    send_email(
        to=args.to,
        subject=args.subject,
        body=args.body,
        cc=args.cc,
        html=args.html,
    )


if __name__ == "__main__":
    main()
