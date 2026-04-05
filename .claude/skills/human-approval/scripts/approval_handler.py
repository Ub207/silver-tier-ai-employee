"""
approval_handler.py — Human Approval skill
Manages the HITL approval gate: submit, check, approve, reject, list.

Usage:
    python approval_handler.py --action submit  --file <filename>
    python approval_handler.py --action check   --file <filename>
    python approval_handler.py --action approve --file <filename> [--reason "..."]
    python approval_handler.py --action reject  --file <filename> [--reason "..."]
    python approval_handler.py --action list
"""

import os
import sys
import io
import re
import shutil
import argparse
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT            = Path(__file__).resolve().parents[3] / "AI_Employee_Vault"
PENDING          = VAULT / "Pending_Approval"
APPROVED         = VAULT / "Approved"
REJECTED         = VAULT / "Rejected"
NEEDS_ACTION     = VAULT / "Needs_Action"
INBOX            = VAULT / "Inbox"
DONE             = VAULT / "Done"
APPROVAL_LOG     = VAULT / "Approval_Log.md"

ALL_FOLDERS = [INBOX, NEEDS_ACTION, PENDING, APPROVED, REJECTED, DONE]

for folder in ALL_FOLDERS:
    folder.mkdir(parents=True, exist_ok=True)

FOLDER_STATUS = {
    "Inbox":            "new",
    "Needs_Action":     "pending",
    "Pending_Approval": "awaiting_approval",
    "Approved":         "approved",
    "Rejected":         "rejected",
    "Done":             "done",
}


# ── Frontmatter helpers ────────────────────────────────────────────────────────

def read_frontmatter(filepath: Path) -> dict:
    meta = {}
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            return meta
        for line in text.split("\n")[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
    except Exception:
        pass
    return meta


def update_frontmatter_field(filepath: Path, field: str, value: str):
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
        if re.search(rf"^{field}:\s*\S*", text, re.MULTILINE):
            updated = re.sub(rf"^({field}:\s*)\S*", rf"\g<1>{value}", text, flags=re.MULTILINE)
        elif text.startswith("---"):
            updated = re.sub(r"^(---\n)", rf"\1{field}: {value}\n", text, count=1)
        else:
            updated = f"---\n{field}: {value}\n---\n\n{text}"
        filepath.write_text(updated, encoding="utf-8")
    except Exception as e:
        print(f"    [WARN] Could not update frontmatter field '{field}': {e}")


def append_rejection_note(filepath: Path, reason: str):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        note = f"\n\n---\n\n## Rejection Record\n\n- **Rejected at:** {now}\n- **Reason:** {reason}\n"
        with filepath.open("a", encoding="utf-8") as f:
            f.write(note)
    except Exception as e:
        print(f"    [WARN] Could not append rejection note: {e}")


# ── Audit log ──────────────────────────────────────────────────────────────────

def append_log(action: str, filename: str, from_folder: str, to_folder: str, note: str = ""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"| {now} | {action.upper()} | {filename} | {from_folder} | {to_folder} | {note or '—'} |\n"
    try:
        if not APPROVAL_LOG.exists():
            APPROVAL_LOG.write_text(
                "# Approval Log\n\n"
                "| Timestamp | Action | File | From | To | Note |\n"
                "|-----------|--------|------|------|----|------|\n",
                encoding="utf-8",
            )
        with APPROVAL_LOG.open("a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"    [WARN] Could not write to Approval_Log.md: {e}")


# ── File finder ────────────────────────────────────────────────────────────────

def find_file(filename: str, preferred_folder: Path = None) -> Path | None:
    search_order = []
    if preferred_folder:
        search_order.append(preferred_folder)
    search_order += [f for f in ALL_FOLDERS if f != preferred_folder]

    for folder in search_order:
        candidate = folder / filename
        if candidate.exists():
            return candidate
    return None


def safe_dest(dest_dir: Path, filename: str) -> Path:
    target = dest_dir / filename
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    counter = 1
    while True:
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def age_str(filepath: Path) -> str:
    try:
        delta = datetime.now().timestamp() - filepath.stat().st_mtime
        minutes = int(delta // 60)
        if minutes < 60:
            return f"{minutes} min ago"
        hours = int(minutes // 60)
        if hours < 24:
            return f"{hours} hr ago"
        return f"{int(hours // 24)} day(s) ago"
    except Exception:
        return "unknown age"


# ── Actions ────────────────────────────────────────────────────────────────────

def action_submit(filename: str, dry: bool):
    src = find_file(filename)
    if not src:
        print(f"[ERROR] File not found in any vault folder: {filename}")
        sys.exit(1)

    if src.parent == PENDING:
        print(f"[INFO] {filename} is already in Pending_Approval/")
        return

    dest = safe_dest(PENDING, src.name)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if dry:
        print(f"[DRY] Would submit: {src.parent.name}/{src.name} -> Pending_Approval/{dest.name}")
        return

    shutil.move(str(src), str(dest))
    update_frontmatter_field(dest, "status", "awaiting_approval")
    append_log("SUBMIT", src.name, src.parent.name, "Pending_Approval")

    print(f"[OK] Submitted for approval: {dest.name}")
    print(f"     Location : Pending_Approval/{dest.name}")
    print(f"     Status   : awaiting_approval")
    print(f"     Time     : {now}")


def action_check(filename: str):
    src = find_file(filename)
    if not src:
        print(f"[ERROR] File not found in any vault folder: {filename}")
        sys.exit(1)

    meta   = read_frontmatter(src)
    status = meta.get("status", "unknown")
    folder = src.parent.name

    print(f"[INFO] {src.name}")
    print(f"       Status   : {status}")
    print(f"       Location : {folder}/")
    print(f"       Age      : {age_str(src)}")

    if status == "awaiting_approval":
        print(f"\n       Run with --action approve or --action reject to decide.")


def action_approve(filename: str, reason: str, dry: bool):
    src = find_file(filename, preferred_folder=PENDING)
    if not src:
        print(f"[ERROR] File not found: {filename}")
        sys.exit(1)

    if src.parent != PENDING:
        print(f"[WARN] File is in {src.parent.name}/, not Pending_Approval/")
        meta = read_frontmatter(src)
        status = meta.get("status", "unknown")
        print(f"       Current status: {status}")
        if status == "approved":
            print("       Already approved.")
            return
        print("       Proceeding with approval from current location.")

    dest = safe_dest(APPROVED, src.name)
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if dry:
        print(f"[DRY] Would approve: {src.parent.name}/{src.name} -> Approved/{dest.name}")
        return

    shutil.move(str(src), str(dest))
    update_frontmatter_field(dest, "status", "approved")
    append_log("APPROVE", src.name, src.parent.name, "Approved", reason)

    print(f"[OK] Approved: {dest.name}")
    print(f"     Moved to : Approved/{dest.name}")
    print(f"     Note     : {reason or '—'}")
    print(f"     Time     : {now}")
    print(f"\n     Task is now cleared for execution.")


def action_reject(filename: str, reason: str, dry: bool):
    src  = find_file(filename, preferred_folder=PENDING)
    if not src:
        print(f"[ERROR] File not found: {filename}")
        sys.exit(1)

    meta = read_frontmatter(src)
    is_financial = meta.get("financial_flag", "").lower() == "true"

    if is_financial and not reason:
        print("[ERROR] A rejection reason is required for financial tasks (financial_flag: true).")
        print("        Add --reason \"...\" to your command.")
        sys.exit(1)

    dest = safe_dest(REJECTED, src.name)
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if dry:
        print(f"[DRY] Would reject: {src.parent.name}/{src.name} -> Rejected/{dest.name}")
        return

    shutil.move(str(src), str(dest))
    update_frontmatter_field(dest, "status", "rejected")
    if reason:
        append_rejection_note(dest, reason)
    append_log("REJECT", src.name, src.parent.name, "Rejected", reason)

    print(f"[OK] Rejected: {dest.name}")
    print(f"     Moved to : Rejected/{dest.name}")
    print(f"     Reason   : {reason or '—'}")
    print(f"     Time     : {now}")


def action_list():
    files = sorted(PENDING.glob("*.md"))
    if not files:
        print("Pending Approval -- no files awaiting review")
        return

    print(f"Pending Approval -- {len(files)} file(s) awaiting review")
    for i, fp in enumerate(files, 1):
        meta    = read_frontmatter(fp)
        ftype   = meta.get("type", "unknown")
        from_f  = meta.get("from", meta.get("sender", "—"))
        age     = age_str(fp)
        print(f"  {i}. {fp.name:<45} | type: {ftype:<20} | from: {from_f:<20} | {age}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Human Approval — Silver Tier AI Employee")
    parser.add_argument("--action", required=True,
                        choices=["submit", "check", "approve", "reject", "list"],
                        help="Action to perform")
    parser.add_argument("--file",   help="Target file name")
    parser.add_argument("--reason", default="", help="Reason (for approve/reject)")
    parser.add_argument("--dry",    action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if args.dry:
        print("DRY RUN MODE -- no files will be moved\n")

    if args.action == "list":
        action_list()
        return

    if not args.file:
        print(f"[ERROR] --file is required for action '{args.action}'")
        sys.exit(1)

    if args.action == "submit":
        action_submit(args.file, args.dry)
    elif args.action == "check":
        action_check(args.file)
    elif args.action == "approve":
        action_approve(args.file, args.reason, args.dry)
    elif args.action == "reject":
        action_reject(args.file, args.reason, args.dry)


if __name__ == "__main__":
    main()
