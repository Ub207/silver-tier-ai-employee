import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

def _load_env():
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def send_email(to: str, subject: str, body: str):
    _load_env()
    sender = os.environ.get("EMAIL_ADDRESS", "").strip()
    password = os.environ.get("EMAIL_PASSWORD", "").strip()

    if not sender or not password:
        raise RuntimeError("Missing EMAIL_ADDRESS/EMAIL_PASSWORD in environment (.env)")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)
        server.send_message(msg)

if __name__ == "__main__":
    # Example usage (requires .env with EMAIL_ADDRESS/EMAIL_PASSWORD)
    try:
        send_email("test@demo.com", "Test", "Hello from AI!")
        print("Email sent!")
    except Exception as e:
        print(f"Error: {e}")
