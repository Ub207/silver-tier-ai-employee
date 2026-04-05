"""
cleanup_plans.py — Archive old Plans and stale Needs_Action emails

Actions:
  1. Move Plans/PLAN_*.md older than --days (default 14) → Plans/Archive/
  2. Move Needs_Action/EMAIL_*.md with status: awaiting_approval → Done/Archived_Emails/
     (these already have plans and approval items; they're just sitting in Needs_Action)

Usage:
    python cleanup_plans.py              # dry run — shows what WOULD be moved
    python cleanup_plans.py --execute    # actually move the files
    python cleanup_plans.py --days 7     # use 7-day cutoff instead of 14
"""

import argparse
import shutil
from datetime import datetime, timedelta
from pathlib import Path

VAULT          = Path("silver_tier")
PLANS          = VAULT / "Plans"
PLANS_ARCHIVE  = PLANS / "Archive"
NEEDS_ACTION   = VAULT / "Needs_Action"
DONE_ARCHIVE   = VAULT / "Done" / "Archived_Emails"


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


def cleanup(days: int, execute: bool):
    PLANS_ARCHIVE.mkdir(parents=True, exist_ok=True)
    DONE_ARCHIVE.mkdir(parents=True, exist_ok=True)

    cutoff = datetime.now() - timedelta(days=days)
    label = "MOVED" if execute else "WOULD MOVE"

    # ── 1. Archive old Plans ────────────────────────────────────────────────
    old_plans = [
        f for f in PLANS.glob("PLAN_*.md")
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff
    ]
    print(f"\n[Plans Cleanup] Files older than {days} days: {len(old_plans)}")
    moved_plans = 0
    for f in old_plans:
        dest = PLANS_ARCHIVE / f.name
        if execute:
            shutil.move(str(f), dest)
        moved_plans += 1
        if moved_plans <= 10:
            print(f"  {label}: {f.name}")

    if moved_plans > 10:
        print(f"  ... and {moved_plans - 10} more")
    print(f"  Total plans {label.lower()}: {moved_plans}")

    # ── 2. Move stale awaiting_approval emails from Needs_Action ───────────
    stale_emails = []
    for f in NEEDS_ACTION.glob("EMAIL_*.md"):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            meta = parse_frontmatter(text)
            if meta.get("status") == "awaiting_approval":
                stale_emails.append(f)
        except Exception:
            pass

    print(f"\n[Needs_Action Cleanup] Emails with awaiting_approval status: {len(stale_emails)}")
    moved_emails = 0
    for f in stale_emails:
        dest = DONE_ARCHIVE / f.name
        if execute:
            shutil.move(str(f), dest)
        moved_emails += 1
        if moved_emails <= 10:
            print(f"  {label}: {f.name}")

    if moved_emails > 10:
        print(f"  ... and {moved_emails - 10} more")
    print(f"  Total emails {label.lower()}: {moved_emails}")

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{'Done.' if execute else 'Dry run -- nothing moved. Run with --execute to apply.'}")
    if not execute:
        print(f"  Command: python cleanup_plans.py --execute --days {days}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Archive old Plans and stale Needs_Action emails")
    parser.add_argument("--execute", action="store_true", help="Actually move files (default: dry run)")
    parser.add_argument("--days", type=int, default=14, help="Age cutoff in days (default: 14)")
    args = parser.parse_args()

    cleanup(days=args.days, execute=args.execute)
