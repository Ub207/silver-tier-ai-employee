"""
ceo_briefing.py — Monday Morning CEO Briefing Generator

Reads Business_Goals.md, Done/, Plans/, and Approval_Log.md then writes
a weekly Briefings/YYYY-MM-DD_Monday_Briefing.md with:
  - Revenue summary
  - Completed tasks this week
  - Bottlenecks (plans that stalled)
  - LinkedIn post count
  - Pending approvals count
  - Proactive suggestions (stale plans, overdue items)

Designed to run every Sunday night via Task Scheduler or cron.

Usage:
    python ceo_briefing.py              # generate for current week
    python ceo_briefing.py --dry        # print to console only, no file write
    python ceo_briefing.py --week 2026-04-01   # generate for specific week (Monday date)
"""

import os
import sys
import io
import re
import argparse
from pathlib import Path
from datetime import datetime, timedelta

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT         = Path("silver_tier")
DONE          = VAULT / "Done"
PLANS         = VAULT / "Plans"
PENDING       = VAULT / "Pending_Approval"
APPROVED      = VAULT / "Approved"
BRIEFINGS     = VAULT / "Briefings"
BUSINESS_GOALS = VAULT / "Business_Goals.md"
APPROVAL_LOG  = VAULT / "Approval_Log.md"
LI_DRAFTS     = VAULT / "LinkedIn_Drafts"

BRIEFINGS.mkdir(parents=True, exist_ok=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

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


def load_env():
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def week_range(anchor: datetime):
    """Return (start, end) for the week containing anchor (Mon–Sun)."""
    monday = anchor - timedelta(days=anchor.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return monday, sunday


def files_in_period(folder: Path, start: datetime, end: datetime, glob: str = "*.md") -> list:
    """Return files whose mtime falls within [start, end]."""
    results = []
    for f in folder.glob(glob):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if start <= mtime <= end:
                results.append(f)
        except Exception:
            pass
    return results


# ── Data collectors ────────────────────────────────────────────────────────────

def collect_completed_tasks(start: datetime, end: datetime) -> list[dict]:
    """Find tasks moved to Done/ during the period."""
    tasks = []
    for f in files_in_period(DONE, start, end):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            meta = parse_frontmatter(text)
            item_type = meta.get("type", "unknown")
            subject = meta.get("subject", meta.get("from", f.stem[:50]))
            tasks.append({
                "file": f.name,
                "type": item_type,
                "subject": subject,
                "mtime": datetime.fromtimestamp(f.stat().st_mtime),
            })
        except Exception:
            tasks.append({"file": f.name, "type": "unknown", "subject": f.stem, "mtime": None})
    return tasks


def collect_stalled_plans(start: datetime, end: datetime) -> list[dict]:
    """Plans created this week that are still active (not done)."""
    stalled = []
    for f in files_in_period(PLANS, start, end, "PLAN_*.md"):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            meta = parse_frontmatter(text)
            if meta.get("status", "active") not in ("done", "completed", "archived"):
                stalled.append({
                    "file": f.name,
                    "context": meta.get("context", f.stem[:60]),
                    "priority": meta.get("priority", "medium"),
                    "created": meta.get("created", "—"),
                })
        except Exception:
            pass
    return stalled


def collect_linkedin_activity(start: datetime, end: datetime) -> dict:
    """Count LinkedIn drafts and pending posts created this week."""
    co_drafts = files_in_period(LI_DRAFTS, start, end, "LI_CO_*.md")
    personal_drafts = files_in_period(LI_DRAFTS, start, end, "LI_PERSONAL_*.md")
    co_pending = files_in_period(PENDING, start, end, "LI_CO_*.md")
    personal_pending = files_in_period(PENDING, start, end, "LI_PERSONAL_*.md")
    return {
        "company_drafts": len(co_drafts),
        "personal_drafts": len(personal_drafts),
        "company_pending": len(co_pending),
        "personal_pending": len(personal_pending),
        "total_drafts": len(co_drafts) + len(personal_drafts),
        "total_pending": len(co_pending) + len(personal_pending),
    }


def collect_approval_activity(start: datetime, end: datetime) -> dict:
    """Count approvals + rejections from Approval_Log.md."""
    approved_count = 0
    rejected_count = 0
    email_sent = 0
    linkedin_posted = 0

    if APPROVAL_LOG.exists():
        try:
            text = APPROVAL_LOG.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                # Count lines with timestamps in this week
                ts_match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line)
                if ts_match:
                    try:
                        ts = datetime.strptime(ts_match.group(), "%Y-%m-%d %H:%M:%S")
                        if start <= ts <= end:
                            if "approved" in line.lower():
                                approved_count += 1
                            if "rejected" in line.lower():
                                rejected_count += 1
                            if "email" in line.lower() and "sent" in line.lower():
                                email_sent += 1
                            if "linkedin" in line.lower():
                                linkedin_posted += 1
                    except Exception:
                        pass
        except Exception:
            pass

    # Also count by scanning Approved/ folder
    approved_this_week = files_in_period(APPROVED, start, end)
    done_this_week = files_in_period(DONE, start, end)

    return {
        "approvals": approved_count or len(approved_this_week),
        "rejections": rejected_count,
        "emails_sent": email_sent,
        "linkedin_actions": linkedin_posted,
        "tasks_done": len(done_this_week),
    }


def read_business_goals() -> dict:
    """Parse Business_Goals.md for KPIs and targets."""
    goals = {
        "revenue_target": "—",
        "current_mtd": "—",
        "primary_goals": [],
        "kpis": [],
        "offers": [],
    }
    if not BUSINESS_GOALS.exists():
        return goals
    try:
        text = BUSINESS_GOALS.read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(text)

        # Extract revenue target
        m = re.search(r"Monthly goal:\s*(.+)", text)
        if m:
            goals["revenue_target"] = m.group(1).strip()

        m = re.search(r"Current MTD:\s*(.+)", text)
        if m:
            goals["current_mtd"] = m.group(1).strip()

        # Extract primary goals (checkboxes)
        for line in text.splitlines():
            if re.match(r"- \[[ x]\]", line):
                done = "[x]" in line.lower()
                text_part = re.sub(r"- \[[ x]\]\s*", "", line).strip()
                goals["primary_goals"].append({"done": done, "text": text_part})

    except Exception as e:
        goals["error"] = str(e)
    return goals


def generate_suggestions(stalled: list, pending_count: int, li: dict) -> list[str]:
    """Generate proactive suggestions based on current state."""
    suggestions = []

    if pending_count > 5:
        suggestions.append(
            f"**Approval Queue**: {pending_count} items waiting in Pending_Approval/. "
            "Consider reviewing and clearing to keep the workflow moving."
        )

    if stalled:
        high_priority = [p for p in stalled if p.get("priority") in ("high", "critical")]
        if high_priority:
            suggestions.append(
                f"**Stalled High-Priority Plans**: {len(high_priority)} high/critical priority plans "
                "from this week have not been completed. Review: "
                + ", ".join(p["context"][:40] for p in high_priority[:3])
            )

    if li["total_drafts"] == 0:
        suggestions.append(
            "**LinkedIn Content**: No LinkedIn posts drafted this week. "
            "Run `python linkedin_scheduler.py` to generate this week's content."
        )
    elif li["total_pending"] > 0 and li["total_drafts"] > 0:
        suggestions.append(
            f"**LinkedIn Posts Pending**: {li['total_pending']} LinkedIn posts are drafted and waiting "
            "in Pending_Approval/. Review and approve to maintain posting schedule."
        )

    if not stalled and pending_count == 0:
        suggestions.append(
            "**Clean Queue**: All plans completed and no pending approvals. "
            "Good week — consider reviewing Business_Goals.md KPIs for next week targets."
        )

    return suggestions


# ── AI enrichment (optional) ───────────────────────────────────────────────────

def _ai_summary(data: dict) -> str:
    """Ask Claude/Ollama for a 2-3 sentence executive summary."""
    load_env()

    completed = data.get("completed_count", 0)
    stalled = data.get("stalled_count", 0)
    pending = data.get("pending_count", 0)
    li_drafts = data.get("li_drafts", 0)

    prompt = f"""You are an AI business assistant writing a Monday Morning CEO briefing summary.
Based on this week's data:
- Tasks completed and moved to Done: {completed}
- Plans created but not yet executed: {stalled}
- Items waiting for human approval: {pending}
- LinkedIn posts drafted: {li_drafts}
- Revenue target: {data.get("revenue_target", "not set")}
- Current MTD: {data.get("current_mtd", "not set")}

Write a 2-3 sentence executive summary for the CEO. Be direct and honest.
Focus on: overall momentum, biggest bottleneck, and one specific action to take today."""

    # Try Ollama first
    ollama_model = os.environ.get("OLLAMA_MODEL", "").strip()
    if ollama_model:
        try:
            import urllib.request
            import json
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            req = urllib.request.Request(
                f"{base_url}/api/generate",
                data=json.dumps({"model": ollama_model, "prompt": prompt, "stream": False}).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())["response"].strip()
        except Exception as e:
            print(f"  [AI] Ollama unavailable ({e}), trying Anthropic...")

    # Try Anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            return resp.content[0].text.strip()
        except Exception as e:
            print(f"  [AI] Anthropic unavailable ({e})")

    return "AI summary unavailable — review metrics below manually."


# ── Briefing writer ────────────────────────────────────────────────────────────

def generate_briefing(week_start: datetime, dry: bool = False):
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    now = datetime.now()
    monday_str = week_start.strftime("%Y-%m-%d")

    print(f"\nGenerating CEO Briefing for week: {monday_str} — {week_end.strftime('%Y-%m-%d')}")

    # Collect all data
    completed = collect_completed_tasks(week_start, week_end)
    stalled   = collect_stalled_plans(week_start, week_end)
    li        = collect_linkedin_activity(week_start, week_end)
    approvals = collect_approval_activity(week_start, week_end)
    goals     = read_business_goals()
    pending_all = list(PENDING.glob("*.md"))

    print(f"  Completed tasks: {len(completed)}")
    print(f"  Stalled plans:   {len(stalled)}")
    print(f"  LinkedIn drafts: {li['total_drafts']}")
    print(f"  Pending approvals (all time): {len(pending_all)}")

    # AI executive summary
    ai_data = {
        "completed_count": len(completed),
        "stalled_count": len(stalled),
        "pending_count": len(pending_all),
        "li_drafts": li["total_drafts"],
        "revenue_target": goals["revenue_target"],
        "current_mtd": goals["current_mtd"],
    }
    print("  Generating AI executive summary...")
    exec_summary = _ai_summary(ai_data)

    # Suggestions
    suggestions = generate_suggestions(stalled, len(pending_all), li)

    # Build markdown tables
    completed_rows = "\n".join(
        f"| {t['type']} | {t['subject'][:60]} | {t['mtime'].strftime('%a %b %d') if t['mtime'] else '—'} |"
        for t in completed[:20]
    ) or "| — | No tasks completed this week | — |"

    stalled_rows = "\n".join(
        f"| {p['priority'].upper()} | {p['context'][:60]} | {p['created'][:10]} |"
        for p in stalled[:10]
    ) or "| — | No stalled plans | — |"

    goals_rows = "\n".join(
        f"| {'[x]' if g['done'] else '[ ]'} | {g['text'][:70]} |"
        for g in goals["primary_goals"]
    ) or "| — | No goals defined — update Business_Goals.md |"

    suggestions_text = "\n\n".join(f"- {s}" for s in suggestions) if suggestions else "- No suggestions this week — clean state."

    pending_items = [f.name for f in pending_all[:5]]
    pending_preview = "\n".join(f"- {n}" for n in pending_items)
    if len(pending_all) > 5:
        pending_preview += f"\n- ... and {len(pending_all) - 5} more"
    if not pending_items:
        pending_preview = "- None — queue is clear"

    briefing = f"""---
generated: {now.strftime("%Y-%m-%d %H:%M:%S")}
week_start: {monday_str}
week_end: {week_end.strftime("%Y-%m-%d")}
type: ceo_briefing
---

# Monday Morning CEO Briefing
*Week of {week_start.strftime("%B %d")} — {week_end.strftime("%B %d, %Y")}*
*Generated: {now.strftime("%Y-%m-%d %H:%M")}*

---

## Executive Summary

{exec_summary}

---

## Revenue
| Metric | Value |
|--------|-------|
| Monthly Target | {goals["revenue_target"]} |
| Current MTD | {goals["current_mtd"]} |
| Revenue Status | Update manually in Business_Goals.md |

---

## This Week's Activity
| Category | Count |
|----------|-------|
| Tasks completed (moved to Done/) | {len(completed)} |
| Approvals processed | {approvals["approvals"]} |
| Rejections | {approvals["rejections"]} |
| LinkedIn posts drafted | {li["total_drafts"]} |
| LinkedIn posts pending approval | {li["total_pending"]} |
| Plans created (stalled) | {len(stalled)} |

---

## Completed Tasks
| Type | Subject | Completed |
|------|---------|-----------|
{completed_rows}

---

## Bottlenecks (Active Plans Not Yet Executed)
| Priority | Plan | Created |
|----------|------|---------|
{stalled_rows}

---

## Q1 2026 Goals Progress
| Status | Goal |
|--------|------|
{goals_rows}

---

## Pending Approval Queue ({len(pending_all)} items)
{pending_preview}

---

## Proactive Suggestions

{suggestions_text}

---

## Actions for This Week
- [ ] Review and clear Pending_Approval/ queue
- [ ] Update Revenue MTD in Business_Goals.md
- [ ] Approve/reject any pending LinkedIn posts
- [ ] Review stalled high-priority plans

---

*Generated by Silver Tier AI Employee — `python ceo_briefing.py`*
"""

    if dry:
        print("\n" + "="*60)
        print(briefing)
        print("="*60)
        print("\nDry run — no file written.")
        return

    out_path = BRIEFINGS / f"{monday_str}_Monday_Briefing.md"
    out_path.write_text(briefing, encoding="utf-8")
    print(f"\nBriefing written to: {out_path}")
    return out_path


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate Monday Morning CEO Briefing")
    parser.add_argument("--dry", action="store_true", help="Print to console, don't write file")
    parser.add_argument("--week", type=str, default=None,
                        help="Week start date (Monday) as YYYY-MM-DD. Defaults to current week.")
    args = parser.parse_args()

    load_env()

    if args.week:
        try:
            anchor = datetime.strptime(args.week, "%Y-%m-%d")
        except ValueError:
            print(f"Invalid date: {args.week}. Use YYYY-MM-DD format.")
            sys.exit(1)
    else:
        anchor = datetime.now()

    # Always snap to Monday of that week
    week_start, _ = week_range(anchor)
    generate_briefing(week_start, dry=args.dry)


if __name__ == "__main__":
    main()
