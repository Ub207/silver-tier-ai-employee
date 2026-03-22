"""
move_task.py — Vault File Manager skill
Moves task files between vault workflow folders and updates frontmatter status.

Usage:
    python move_task.py --file <filename> --to <folder>
    python move_task.py --pattern "WA_*.md" --from Pending_Approval --to Done
    python move_task.py --status
    python move_task.py --file <filename> --to <folder> --dry
"""

import os
import sys
import io
import re
import shutil
import argparse
import fnmatch
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT = Path(__file__).resolve().parents[3] / "AI_Employee_Vault"

FOLDERS = {
    "Inbox":            "new",
    "Needs_Action":     "pending",
    "Pending_Approval": "awaiting_approval",
    "Approved":         "approved",
    "Rejected":         "rejected",
    "Done":             "done",
}

APPROVAL_LOG = VAULT / "Approval_Log.md"

for folder in FOLDERS:
    (VAULT / folder).mkdir(parents=True, exist_ok=True)


# ── Frontmatter helpers ────────────────────────────────────────────────────────

def update_frontmatter_status(filepath: Path, new_status: str):
    """Update or insert the status: field in YAML frontmatter."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^status:\s*\S+", text, re.MULTILINE):
            updated = re.sub(r"^(status:\s*)\S+", rf"\g<1>{new_status}", text, flags=re.MULTILINE)
        elif text.startswith("---"):
            # Insert after opening ---
            updated = re.sub(r"^(---\n)", rf"\1status: {new_status}\n", text, count=1)
        else:
            updated = f"---\nstatus: {new_status}\n---\n\n{text}"
        filepath.write_text(updated, encoding="utf-8")
    except Exception as e:
        print(f"    [WARN] Could not update frontmatter: {e}")


# ── Audit log ──────────────────────────────────────────────────────────────────

def append_log(filename: str, from_folder: str, to_folder: str, note: str = ""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"| {now} | {filename} | {from_folder} | {to_folder} | {note or '—'} |\n"
    try:
        if not APPROVAL_LOG.exists():
            APPROVAL_LOG.write_text(
                "# Approval Log\n\n"
                "| Timestamp | File | From | To | Note |\n"
                "|-----------|------|------|----|------|\n",
                encoding="utf-8",
            )
        with APPROVAL_LOG.open("a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"    [WARN] Could not write to Approval_Log.md: {e}")


# ── File finder ────────────────────────────────────────────────────────────────

def find_file(filename: str, from_folder: str = None) -> Path | None:
    """Locate a file by name in the vault. Searches from_folder first, then all folders."""
    search_order = []
    if from_folder:
        search_order.append(VAULT / from_folder)
    search_order += [VAULT / f for f in FOLDERS if f != from_folder]

    for folder in search_order:
        candidate = folder / filename
        if candidate.exists():
            return candidate
    return None


def find_by_pattern(pattern: str, from_folder: str) -> list[Path]:
    """Find all files in a folder matching a glob pattern."""
    folder_path = VAULT / from_folder
    if not folder_path.exists():
        return []
    return [f for f in folder_path.iterdir() if fnmatch.fnmatch(f.name, pattern) and f.is_file()]


def resolve_dest(dest_name: str) -> Path:
    """Resolve destination folder name (case-insensitive)."""
    for folder in FOLDERS:
        if folder.lower() == dest_name.lower():
            return VAULT / folder
    return None


def safe_dest_path(dest_dir: Path, filename: str) -> Path:
    """Return a non-conflicting destination path, adding _1, _2 suffix if needed."""
    target = dest_dir / filename
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


# ── Actions ────────────────────────────────────────────────────────────────────

def move_file(filename: str, to_name: str, from_name: str = None,
              note: str = "", dry: bool = False) -> bool:
    src = find_file(filename, from_name)
    if not src:
        search_scope = from_name or "all vault folders"
        print(f"[ERROR] File not found: {filename} (searched {search_scope})")
        return False

    dest_dir = resolve_dest(to_name)
    if dest_dir is None:
        print(f"[ERROR] Unknown destination folder: {to_name}")
        print(f"        Valid folders: {', '.join(FOLDERS.keys())}")
        return False

    from_folder = src.parent.name
    new_status  = FOLDERS.get(dest_dir.name, "pending")
    dest_path   = safe_dest_path(dest_dir, src.name)

    if dry:
        print(f"[DRY] Would move: {from_folder}/{src.name}")
        print(f"             ->  {dest_dir.name}/{dest_path.name}")
        print(f"      Status  : {new_status}")
        return True

    shutil.move(str(src), str(dest_path))
    update_frontmatter_status(dest_path, new_status)
    append_log(src.name, from_folder, dest_dir.name, note)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[OK] Moved: {from_folder}/{src.name}")
    print(f"         -> {dest_dir.name}/{dest_path.name}")
    print(f"     Status updated : {new_status}")
    print(f"     Logged at      : {now}")
    return True


def move_pattern(pattern: str, from_name: str, to_name: str,
                 note: str = "", dry: bool = False) -> int:
    files = find_by_pattern(pattern, from_name)
    if not files:
        print(f"[WARN] No files matching '{pattern}' found in {from_name}/")
        return 0

    print(f"Found {len(files)} file(s) matching '{pattern}' in {from_name}/")
    success = 0
    for f in files:
        ok = move_file(f.name, to_name, from_name, note, dry)
        if ok:
            success += 1
    return success


def print_status():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Vault Status -- {now}")
    for folder in FOLDERS:
        folder_path = VAULT / folder
        count = len(list(folder_path.glob("*.md"))) if folder_path.exists() else 0
        print(f"  {folder:<20}: {count:>3} file(s)")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Vault File Manager — Silver Tier AI Employee")
    parser.add_argument("--file",    help="File name to move")
    parser.add_argument("--to",      help="Destination folder")
    parser.add_argument("--from",    dest="from_folder", help="Source folder (optional)")
    parser.add_argument("--pattern", help="Glob pattern to move multiple files")
    parser.add_argument("--note",    default="", help="Note to append to Approval_Log.md")
    parser.add_argument("--status",  action="store_true", help="Print vault folder counts and exit")
    parser.add_argument("--dry",     action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if args.dry:
        print("DRY RUN MODE -- no files will be moved\n")

    if args.status:
        print_status()
        return

    if args.pattern:
        if not args.from_folder:
            print("[ERROR] --pattern requires --from <folder>")
            sys.exit(1)
        if not args.to:
            print("[ERROR] --pattern requires --to <folder>")
            sys.exit(1)
        count = move_pattern(args.pattern, args.from_folder, args.to, args.note, args.dry)
        print(f"\nTotal moved: {count} file(s)")
        return

    if not args.file:
        print("[ERROR] Provide --file <filename>, --pattern <glob>, or --status")
        sys.exit(1)
    if not args.to:
        print("[ERROR] Provide --to <destination folder>")
        sys.exit(1)

    ok = move_file(args.file, args.to, args.from_folder, args.note, args.dry)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
