"""
approval_executor.py — Silver Tier Action Executor

Monitors the vault/Approved/ folder.
When a human approves a task, this script reads the file type and executes
the real-world action: send email via SMTP, post to LinkedIn, or log WA reply.

This is the final link in the approval loop:
  Pending_Approval/ → Human approves → Approved/ → THIS SCRIPT → Done/

Usage:
    python approval_executor.py           # watch mode (continuous)
    python approval_executor.py --once    # process current Approved/ files and exit
    python approval_executor.py --dry     # preview actions without executing
"""

import os
import sys
import io
import re
import time
import shutil
import smtplib
import argparse
import json
from pathlib import Path
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT        = Path("silver_tier")
APPROVED     = VAULT / "Approved"
DONE         = VAULT / "Done"
PENDING      = VAULT / "Pending_Approval"
APPROVAL_LOG = VAULT / "Approval_Log.md"
SEEN_FILE    = Path(".executor_seen_ids.json")
POLL_INTERVAL = 20   # seconds between Approved/ scans

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

for folder in [APPROVED, DONE, PENDING]:
    folder.mkdir(parents=True, exist_ok=True)


# ── Env loader ─────────────────────────────────────────────────────────────────

def load_env():
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ── Seen-IDs tracker ───────────────────────────────────────────────────────────

def load_seen() -> set:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")


# ── Frontmatter parser ─────────────────────────────────────────────────────────

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


def set_frontmatter_status(filepath: Path, new_status: str):
    text = filepath.read_text(encoding="utf-8", errors="replace")
    updated = re.sub(r"^(status:\s*)\S+", rf"\g<1>{new_status}", text, flags=re.MULTILINE)
    if updated == text:
        # status field missing — prepend it
        updated = re.sub(r"^(---\n)", rf"\1status: {new_status}\n", text, count=1)
    filepath.write_text(updated, encoding="utf-8")


# ── Audit log ──────────────────────────────────────────────────────────────────

def append_log(action: str, filename: str, result: str, detail: str = ""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"| {now} | EXECUTE | {action} | {filename} | {result} | {detail} |\n"
    try:
        if not APPROVAL_LOG.exists():
            APPROVAL_LOG.write_text(
                "# Approval Log\n\n"
                "| Timestamp | Stage | Action | File | Result | Detail |\n"
                "|-----------|-------|--------|------|--------|--------|\n",
                encoding="utf-8",
            )
        with APPROVAL_LOG.open("a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"    [WARN] Could not write to Approval_Log.md: {e}")


# ── Move to Done ───────────────────────────────────────────────────────────────

def archive_to_done(filepath: Path, status: str = "done"):
    dest = DONE / filepath.name
    counter = 1
    while dest.exists():
        dest = DONE / f"{filepath.stem}_{counter}{filepath.suffix}"
        counter += 1
    shutil.move(str(filepath), str(dest))
    set_frontmatter_status(dest, status)
    return dest


# ── Email executor ─────────────────────────────────────────────────────────────

def execute_email_reply(filepath: Path, meta: dict, body: str, dry: bool) -> dict:
    """
    Parse the approved reply file and send the email via Gmail SMTP.
    Looks for the selected reply text under ## Approved Reply or ## Selected Reply.
    """
    sender   = os.environ.get("EMAIL_ADDRESS", "").strip()
    password = os.environ.get("EMAIL_PASSWORD", "").strip()

    to      = meta.get("to", meta.get("reply_to", meta.get("from", ""))).strip()
    subject = meta.get("subject", "Re: Your message").strip()
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    # Extract approved reply body
    reply_body = _extract_approved_reply(body)

    if not reply_body:
        return {
            "action": "email_reply",
            "status": "skipped",
            "reason": "No approved reply text found in file. Add content under '## Approved Reply'.",
        }

    if not to:
        return {"action": "email_reply", "status": "error", "reason": "No recipient address found in frontmatter."}

    if not sender:
        return {"action": "email_reply", "status": "error", "reason": "EMAIL_ADDRESS not set in .env"}

    if not password:
        return {"action": "email_reply", "status": "error", "reason": "EMAIL_PASSWORD not set in .env"}

    if dry:
        print(f"    [DRY] Would send email:")
        print(f"          To      : {to}")
        print(f"          Subject : {subject}")
        print(f"          Body    : {reply_body[:120]}...")
        return {"action": "email_reply", "status": "dry_run", "to": to, "subject": subject}

    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = sender
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(reply_body, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, password)
            server.sendmail(sender, [to], msg.as_string())

        return {"action": "email_reply", "status": "sent", "to": to, "subject": subject}

    except smtplib.SMTPAuthenticationError:
        return {"action": "email_reply", "status": "error",
                "reason": "Gmail auth failed. Check EMAIL_ADDRESS and EMAIL_PASSWORD (use App Password)."}
    except Exception as e:
        return {"action": "email_reply", "status": "error", "reason": str(e)}


def _extract_approved_reply(body: str) -> str:
    """
    Extract reply content from sections:
      ## Approved Reply
      ## Selected Reply
      ## Reply to Send
    Falls back to content after the last --- separator if none found.
    """
    patterns = [
        r"##\s+Approved Reply\s*\n+([\s\S]+?)(?=\n##|\Z)",
        r"##\s+Selected Reply\s*\n+([\s\S]+?)(?=\n##|\Z)",
        r"##\s+Reply to Send\s*\n+([\s\S]+?)(?=\n##|\Z)",
        r"##\s+Final Reply\s*\n+([\s\S]+?)(?=\n##|\Z)",
    ]
    for pattern in patterns:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    # Fallback: last block after a horizontal rule
    parts = re.split(r"\n---+\n", body)
    if len(parts) > 1:
        candidate = parts[-1].strip()
        if len(candidate) > 20:
            return candidate

    return ""


# ── LinkedIn executor ──────────────────────────────────────────────────────────

def execute_linkedin_post(filepath: Path, meta: dict, body: str, dry: bool) -> dict:
    """
    Post to LinkedIn using linkedin_personal_mcp.py or linkedin_company_mcp.py
    depending on the file prefix.
    """
    is_company = filepath.name.startswith("LI_CO_")
    script = Path("linkedin_company_mcp.py") if is_company else Path("linkedin_personal_mcp.py")

    if not script.exists():
        return {
            "action": "linkedin_post",
            "status": "error",
            "reason": f"{script} not found. Cannot post to LinkedIn.",
        }

    # Extract post content — strip frontmatter
    post_content = body
    if post_content.startswith("---"):
        parts = post_content.split("---", 2)
        if len(parts) >= 3:
            post_content = parts[2].strip()

    # Remove any approval/metadata sections — take content before ## Approval
    content_match = re.split(r"\n##\s+Approval", post_content, maxsplit=1, flags=re.IGNORECASE)
    post_content = content_match[0].strip()

    if len(post_content) < 10:
        return {"action": "linkedin_post", "status": "skipped", "reason": "Post content is empty."}

    if dry:
        account = "company page" if is_company else "personal profile"
        print(f"    [DRY] Would post to LinkedIn ({account}):")
        print(f"          Content : {post_content[:120]}...")
        return {"action": "linkedin_post", "status": "dry_run", "account": account}

    import subprocess
    tmp_file = APPROVED / f"_tmp_post_{filepath.stem}.txt"
    tmp_file.write_text(post_content, encoding="utf-8")

    try:
        result = subprocess.run(
            [sys.executable, str(script), "--post", tmp_file.name],
            capture_output=True,
            text=True,
            timeout=120,
        )
        success = result.returncode == 0
        output  = (result.stdout + result.stderr).strip()
        return {
            "action":  "linkedin_post",
            "status":  "posted" if success else "error",
            "reason":  output if not success else "",
            "account": "company" if is_company else "personal",
        }
    except subprocess.TimeoutExpired:
        return {"action": "linkedin_post", "status": "error", "reason": "LinkedIn post timed out after 120s."}
    except Exception as e:
        return {"action": "linkedin_post", "status": "error", "reason": str(e)}
    finally:
        if tmp_file.exists():
            tmp_file.unlink()


# ── WA reply executor ──────────────────────────────────────────────────────────

def execute_whatsapp_reply(filepath: Path, meta: dict, body: str, dry: bool) -> dict:
    """
    WhatsApp replies cannot be sent programmatically without a business API.
    Log the approved reply so the human can copy-paste it, and archive to Done.
    """
    reply = _extract_approved_reply(body)
    contact = meta.get("from", meta.get("contact", "unknown"))

    if dry:
        print(f"    [DRY] Would log WA reply for {contact}")
        return {"action": "whatsapp_reply", "status": "dry_run"}

    log_entry = (
        f"\n\n---\n\n"
        f"## WA Reply Ready — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"**Contact:** {contact}\n\n"
        f"**Approved reply:**\n\n{reply or '(see file for selected option)'}\n\n"
        f"*Copy the above and send manually via WhatsApp Web.*\n"
    )
    try:
        with filepath.open("a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass

    return {"action": "whatsapp_reply", "status": "logged", "contact": contact}


# ── Dispatcher ─────────────────────────────────────────────────────────────────

def process_approved_file(filepath: Path, dry: bool) -> dict:
    raw  = filepath.read_text(encoding="utf-8", errors="replace")
    meta = parse_frontmatter(raw)
    file_type = meta.get("type", "").lower()
    name = filepath.name

    print(f"\n  Executing: {name}  (type: {file_type or 'unknown'})")

    # Dispatch by file type or name prefix
    if file_type in ("email_reply", "email") or name.startswith("REPLY_EMAIL_") or name.startswith("EMAIL_REPLY_"):
        result = execute_email_reply(filepath, meta, raw, dry)

    elif file_type in ("linkedin", "linkedin_post") or name.startswith("LI_"):
        result = execute_linkedin_post(filepath, meta, raw, dry)

    elif file_type in ("whatsapp_reply", "whatsapp") or name.startswith("WA_REPLY_") or name.startswith("WA_"):
        result = execute_whatsapp_reply(filepath, meta, raw, dry)

    else:
        print(f"    [WARN] Unknown file type '{file_type}' — logging and archiving.")
        result = {"action": "unknown", "status": "archived", "reason": f"type={file_type}"}

    # Archive to Done on success or non-fatal outcomes
    terminal_statuses = {"sent", "posted", "logged", "archived", "dry_run"}
    if result.get("status") in terminal_statuses and not dry:
        dest = archive_to_done(filepath, status="done")
        result["archived_to"] = dest.name

    # Print result
    status = result.get("status", "?")
    if status == "sent":
        print(f"    [OK] Email sent to {result.get('to')} | Subject: {result.get('subject')}")
    elif status == "posted":
        print(f"    [OK] LinkedIn post published ({result.get('account', '')})")
    elif status == "logged":
        print(f"    [OK] WA reply logged for {result.get('contact')} (send manually)")
    elif status == "dry_run":
        print(f"    [DRY] No action taken.")
    elif status == "skipped":
        print(f"    [SKIP] {result.get('reason', '')}")
    elif status == "error":
        print(f"    [ERROR] {result.get('reason', 'Unknown error')}")

    # Audit log
    append_log(
        action   = result.get("action", "unknown"),
        filename = name,
        result   = status,
        detail   = result.get("reason", result.get("to", result.get("account", ""))),
    )

    return result


# ── Scanner ────────────────────────────────────────────────────────────────────

def scan_approved(seen: set, dry: bool) -> list[dict]:
    files = sorted(APPROVED.glob("*.md"))
    new_files = [f for f in files if not f.name.startswith("_") and f.name not in seen]

    if not new_files:
        return []

    print(f"\nFound {len(new_files)} approved file(s) to execute.")
    results = []

    for filepath in new_files:
        try:
            result = process_approved_file(filepath, dry)
            results.append(result)
            if not dry and result.get("status") not in ("error",):
                seen.add(filepath.name)
        except Exception as e:
            print(f"    [ERROR] Failed to process {filepath.name}: {e}")
            results.append({"file": filepath.name, "status": "error", "reason": str(e)})

    return results


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Silver Tier — Approval Executor")
    parser.add_argument("--once",  action="store_true", help="Process current Approved/ files and exit")
    parser.add_argument("--dry",   action="store_true", help="Preview without executing real actions")
    args = parser.parse_args()

    load_env()

    if args.dry:
        print("DRY RUN MODE -- no emails sent, no posts published\n")

    seen = load_seen() if not args.dry else set()

    if args.once:
        print(f"Scanning {APPROVED} ...")
        results = scan_approved(seen, args.dry)
        if not results:
            print("No approved files to execute.")
        else:
            if not args.dry:
                save_seen(seen)
            ok    = sum(1 for r in results if r.get("status") in ("sent", "posted", "logged"))
            error = sum(1 for r in results if r.get("status") == "error")
            print(f"\nDone. {ok} executed, {error} error(s).")
        return

    # Watch mode
    print(f"Watching {APPROVED}/ every {POLL_INTERVAL}s ... (Ctrl+C to stop)")
    try:
        while True:
            results = scan_approved(seen, args.dry)
            if results and not args.dry:
                save_seen(seen)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
