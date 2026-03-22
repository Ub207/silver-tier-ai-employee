"""
stop_hook.py — Ralph Wiggum Stop Hook

Runs when Claude Code wants to stop. If there is pending work in the vault,
this hook blocks the stop and injects a reminder for Claude to continue.

Exit codes:
  0 = allow stop (no pending work)
  2 = block stop (pending work found — stdout is injected as user message)

Reference: Claude Code hooks documentation (Stop hook)
"""

import sys
import json
from pathlib import Path

VAULT        = Path("D:/silver_tier/silver_tier")
NEEDS_ACTION = VAULT / "Needs_Action"
APPROVED     = VAULT / "Approved"
PENDING      = VAULT / "Pending_Approval"


def count_files(folder: Path, pattern: str = "*.md") -> int:
    if not folder.exists():
        return 0
    return len(list(folder.glob(pattern)))


def main():
    # Read stop hook input (JSON from stdin)
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    # Only count approved items the AI can execute (emails, WA replies) — not LinkedIn
    # posts which require human browser action and can't be auto-resolved.
    approved_items = sum(
        1 for f in APPROVED.glob("*.md")
        if not f.name.startswith("LI_") and not f.name.startswith("_tmp_")
    )

    # Only count files that are truly unprocessed (status: pending, not awaiting_approval)
    def unprocessed(pattern: str) -> int:
        count = 0
        for f in NEEDS_ACTION.glob(pattern):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                # If status is awaiting_approval/approved/done — already handled
                if "status: awaiting_approval" in text or \
                   "status: approved" in text or \
                   "status: done" in text:
                    continue
                count += 1
            except Exception:
                pass
        return count

    wa_count   = unprocessed("WA_*.md")
    plan_count = unprocessed("Plan_*.md")
    drop_count = unprocessed("DROP_*.md")

    actionable = wa_count + plan_count + drop_count + approved_items

    if actionable > 0:
        items = []
        if wa_count:       items.append(f"{wa_count} WA")
        if plan_count:     items.append(f"{plan_count} plan")
        if drop_count:     items.append(f"{drop_count} drop")
        if approved_items: items.append(f"{approved_items} approved")

        summary = ", ".join(items)
        print(f"PENDING WORK DETECTED — do not stop yet.\n\n"
              f"Items requiring action: {summary}\n\n"
              f"Run workflow_runner.py to process Needs_Action, "
              f"then approval_executor.py for any Approved items. "
              f"Continue until all actionable items are handled.",
              flush=True)
        print(f"stop_hook: BLOCKING — {summary}", file=sys.stderr, flush=True)
        sys.exit(2)  # Block stop

    # Nothing actionable — allow Claude to stop
    print("stop_hook: OK — no pending work, allowing stop", file=sys.stderr, flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
