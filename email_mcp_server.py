"""
email_mcp_server.py — Silver Tier Email MCP Server

Exposes Claude Code tools for the email workflow:
  - send_email          : send a real email via Gmail SMTP
  - list_pending_emails : list pending email approval files in vault
  - get_email_draft     : read a specific email approval file

Setup (one-time):
    Add to .mcp.json (already done).
    Requires .env with EMAIL_ADDRESS + EMAIL_PASSWORD (Gmail App Password).

Usage:
    Claude Code calls this server automatically via MCP.
    Human still reviews drafts before they are sent.

Dependencies:
    pip install mcp
"""

import os
import sys
import smtplib
import logging
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("EmailMCP")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT        = Path("D:/silver_tier/silver_tier")
PENDING      = VAULT / "Pending_Approval"
APPROVED     = VAULT / "Approved"
DONE         = VAULT / "Done"
APPROVAL_LOG = VAULT / "Approval_Log.md"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

mcp = FastMCP("Email MCP")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_env():
    """Load .env file variables into os.environ."""
    env_path = Path("D:/silver_tier/.env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _log_action(action: str, details: str):
    """Append entry to Approval_Log.md."""
    if not APPROVAL_LOG.exists():
        APPROVAL_LOG.write_text("# Approval Log\n\n", encoding="utf-8")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## {ts} — {action}\n{details}\n"
    with APPROVAL_LOG.open("a", encoding="utf-8") as f:
        f.write(entry)


# ── Tool 1: send_email ─────────────────────────────────────────────────────────

@mcp.tool()
def send_email(to: str, subject: str, body: str, cc: str = "") -> str:
    """
    Send a real email via Gmail SMTP.

    Args:
        to:      Recipient email address (required)
        subject: Email subject line (required)
        body:    Plain-text email body (required)
        cc:      Optional CC email address

    Returns a success or error message.
    NOTE: Only call this after a human has approved the draft in /Approved/.
    """
    _load_env()
    sender   = os.environ.get("EMAIL_ADDRESS", "").strip()
    password = os.environ.get("EMAIL_PASSWORD", "").strip()

    if not sender or not password:
        return (
            "ERROR: Missing EMAIL_ADDRESS or EMAIL_PASSWORD in .env file. "
            "Add your Gmail address and App Password to D:/silver_tier/.env"
        )

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender
        msg["To"]      = to
        if cc:
            msg["Cc"] = cc

        msg.attach(MIMEText(body, "plain", "utf-8"))

        recipients = [to] + ([cc] if cc else [])

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())

        logger.info(f"Email sent to {to} — subject: {subject}")
        _log_action("Email Sent", f"To: {to}\nSubject: {subject}\nCC: {cc or '—'}")
        return f"✓ Email sent successfully to {to} with subject: '{subject}'"

    except smtplib.SMTPAuthenticationError:
        return (
            "ERROR: Gmail authentication failed. "
            "Ensure EMAIL_PASSWORD is a valid App Password "
            "(not your Gmail account password). "
            "Generate one at myaccount.google.com/apppasswords"
        )
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return f"ERROR: Failed to send email — {type(e).__name__}: {e}"


# ── Tool 2: list_pending_emails ────────────────────────────────────────────────

@mcp.tool()
def list_pending_emails(limit: int = 20) -> str:
    """
    List pending email approval files in the vault.

    Shows EMAIL_*.md files in /Pending_Approval and /Needs_Action
    that are awaiting human review or AI processing.

    Args:
        limit: Maximum number of items to return (default 20)

    Returns a formatted table.
    """
    rows = []

    for folder, label in [(PENDING, "Pending_Approval"), (APPROVED, "Approved")]:
        if not folder.exists():
            continue
        for f in sorted(folder.glob("EMAIL_*.md"))[:limit]:
            text = f.read_text(encoding="utf-8", errors="ignore")
            meta = {}
            if text.startswith("---"):
                for line in text.split("\n")[1:]:
                    if line.strip() == "---":
                        break
                    if ":" in line:
                        k, _, v = line.partition(":")
                        meta[k.strip()] = v.strip()

            subject  = meta.get("subject", "—")[:50]
            sender   = meta.get("from", "—")[:40]
            received = meta.get("received", "—")[:16]
            rows.append(f"| {f.name[:40]} | {label} | {sender} | {subject} | {received} |")

    if not rows:
        return "No pending email approval files found."

    header = (
        "| File | Folder | From | Subject | Received |\n"
        "|------|--------|------|---------|----------|\n"
    )
    return header + "\n".join(rows[:limit])


# ── Tool 3: get_email_draft ────────────────────────────────────────────────────

@mcp.tool()
def get_email_draft(filename: str) -> str:
    """
    Read a specific email draft or approval file from the vault.

    Args:
        filename: The .md filename (e.g. 'EMAIL_20260311_090749_45330.md')

    Searches in Pending_Approval/, Approved/, and Needs_Action/.
    Returns the full file contents.
    """
    search_dirs = [PENDING, APPROVED, VAULT / "Needs_Action"]
    for folder in search_dirs:
        path = folder / filename
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")

    return f"ERROR: File '{filename}' not found in Pending_Approval, Approved, or Needs_Action."


# ── Tool 4: archive_email ─────────────────────────────────────────────────────

@mcp.tool()
def archive_email(filename: str, reason: str = "no action needed") -> str:
    """
    Move an email file to /Done (archive it without replying).

    Use this for newsletters, notifications, or emails that don't require a reply.

    Args:
        filename: The .md filename to archive
        reason:   Why this email is being archived (for the log)

    Returns success or error message.
    """
    search_dirs = [VAULT / "Needs_Action", PENDING, APPROVED]
    for folder in search_dirs:
        src = folder / filename
        if src.exists():
            DONE.mkdir(parents=True, exist_ok=True)
            dst = DONE / filename
            # Avoid overwrite
            if dst.exists():
                dst = DONE / f"{src.stem}_archived_{datetime.now().strftime('%H%M%S')}.md"
            src.rename(dst)
            _log_action("Email Archived", f"File: {filename}\nReason: {reason}")
            logger.info(f"Archived {filename} → Done/")
            return f"✓ Archived '{filename}' to Done/ — reason: {reason}"

    return f"ERROR: File '{filename}' not found in Needs_Action, Pending_Approval, or Approved."


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
