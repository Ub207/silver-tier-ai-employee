"""
inbox_planner.py — Silver Tier Inbox Reasoning Workflow

Watches vault/Inbox/ for new task files.
For each new task:
  1. Reads the task content
  2. Reasons about it using Claude (2-step loop)
  3. Creates Plan_<timestamp>.md in vault/Needs_Action/

Does NOT execute the task — planning only.

Usage:
    python inbox_planner.py           # watch mode (continuous)
    python inbox_planner.py --once    # process current Inbox files and exit
    python inbox_planner.py --dry     # preview plans without writing
"""

import os
import sys
import io
import re
import time
import argparse
from pathlib import Path
from datetime import datetime

# Fix Windows cp1252 encoding issues
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Config ─────────────────────────────────────────────────────────────────────

VAULT        = Path("silver_tier")
INBOX        = VAULT / "Inbox"
NEEDS_ACTION = VAULT / "Needs_Action"
SEEN_FILE    = Path(".inbox_seen_ids.json")
POLL_INTERVAL = 30  # seconds between Inbox scans

for folder in [INBOX, NEEDS_ACTION]:
    folder.mkdir(parents=True, exist_ok=True)


# ── Env loader ─────────────────────────────────────────────────────────────────

def _load_env():
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ── Seen-IDs tracker ───────────────────────────────────────────────────────────

def _load_seen() -> set:
    import json
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def _save_seen(seen: set):
    import json
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")


# ── Claude reasoning loop ──────────────────────────────────────────────────────

def _reason_about_task(task_title: str, task_body: str) -> dict:
    """
    2-step Claude reasoning loop:
      Step 1 — Understand the task deeply
      Step 2 — Build a structured plan

    Returns dict with: objective, steps, priority, requires_approval, suggested_output
    Falls back to defaults if API is unavailable.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        print("    [AI] No ANTHROPIC_API_KEY -- using default plan structure.")
        return _default_plan(task_title)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # ── Step 1: Understand ────────────────────────────────────────────────
        print("    [LOOP-1] Analyzing task...")
        understand_resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": f"""You are an AI business assistant planning tasks for a professional services company.

Read this task carefully and answer concisely:

TASK TITLE: {task_title}
TASK CONTENT:
{task_body[:2000]}

Answer these questions (1-2 sentences each):
1. OBJECTIVE: What is the core goal of this task?
2. COMPLEXITY: How complex is this? (simple/moderate/complex) and why?
3. PRIORITY: What priority level? (Low/Medium/High) and why?
4. APPROVAL_NEEDED: Does a human need to approve anything before this is executed? (yes/no) and why?
5. RISKS: What could go wrong if this task is handled incorrectly?"""}]
        ).content[0].text.strip()

        print("    [LOOP-1] Analysis complete.")

        # ── Step 2: Build structured plan ─────────────────────────────────────
        print("    [LOOP-2] Generating plan...")
        plan_resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": f"""Based on this task analysis:

{understand_resp}

Now create a detailed step-by-step plan. Reply in EXACTLY this format:

OBJECTIVE: [one clear sentence — what this plan achieves]
STEP_1: [concrete action]
STEP_2: [concrete action]
STEP_3: [concrete action]
STEP_4: [concrete action]
STEP_5: [concrete action]
PRIORITY: [High / Medium / Low]
REQUIRES_APPROVAL: [Yes / No]
SUGGESTED_OUTPUT: [what the final deliverable or outcome should look like]

Rules:
- Steps must be concrete and actionable
- Do NOT include steps that execute the task — only plan and prepare
- Keep each step under 120 characters"""}]
        ).content[0].text.strip()

        print("    [LOOP-2] Plan generated.")
        return _parse_plan_response(plan_resp, task_title)

    except Exception as e:
        print(f"    [AI] Error: {e} -- using default plan.")
        return _default_plan(task_title)


def _parse_plan_response(text: str, task_title: str) -> dict:
    """Parse the structured plan response from Claude."""
    def grab(key: str) -> str:
        m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    steps = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"STEP_\d+:", line, re.IGNORECASE):
            step_text = line.split(":", 1)[1].strip()
            if step_text:
                steps.append(step_text)

    if not steps:
        steps = [
            "Review task details and clarify requirements",
            "Identify stakeholders and resources needed",
            "Break down into sub-tasks",
            "Draft execution plan",
            "Present for human review and approval",
        ]

    objective = grab("OBJECTIVE") or f"Complete task: {task_title}"
    priority_raw = grab("PRIORITY").lower()
    priority = "High" if "high" in priority_raw else "Low" if "low" in priority_raw else "Medium"
    approval_raw = grab("REQUIRES_APPROVAL").lower()
    requires_approval = "No" if "no" in approval_raw and "yes" not in approval_raw else "Yes"
    suggested_output = grab("SUGGESTED_OUTPUT") or "Completed task with documented outcome"

    return {
        "objective": objective,
        "steps": steps,
        "priority": priority,
        "requires_approval": requires_approval,
        "suggested_output": suggested_output,
    }


def _default_plan(task_title: str) -> dict:
    return {
        "objective": f"Complete task: {task_title}",
        "steps": [
            "Read and fully understand the task requirements",
            "Identify all stakeholders and dependencies",
            "Break the task into smaller actionable sub-tasks",
            "Draft an execution approach for human review",
            "Await approval before executing",
        ],
        "priority": "Medium",
        "requires_approval": "Yes",
        "suggested_output": "Completed task with documented outcome and confirmation",
    }


# ── Plan writer ────────────────────────────────────────────────────────────────

def create_plan_file(task_file: Path, plan: dict, dry: bool) -> Path | None:
    """Write Plan_<timestamp>.md to Needs_Action/."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    plan_name = f"Plan_{ts}.md"
    plan_path = NEEDS_ACTION / plan_name

    task_body = task_file.read_text(encoding="utf-8", errors="replace")

    steps_md = "\n".join(f"- [ ] {s}" for s in plan["steps"])

    content = f"""---
type: plan
source_file: {task_file.name}
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
priority: {plan["priority"]}
requires_approval: {plan["requires_approval"]}
status: active
---

# Task Plan

*Generated by inbox_planner.py on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
*Source: `Inbox/{task_file.name}`*

---

## Original Task

{task_body.strip()}

---

## Objective

{plan["objective"]}

---

## Step-by-Step Plan

{steps_md}

---

## Priority

**{plan["priority"]}**

---

## Requires Human Approval?

**{plan["requires_approval"]}**

---

## Suggested Output

{plan["suggested_output"]}

---

> **Note:** This is a plan only. No action has been taken.
> Review, approve, and then execute each step manually or via the appropriate workflow.
"""

    if not dry:
        plan_path.write_text(content, encoding="utf-8")

    return plan_path


# ── Core processor ─────────────────────────────────────────────────────────────

def process_inbox_file(task_file: Path, dry: bool) -> dict:
    """Read one Inbox file, reason about it, and create a plan."""
    print(f"\n  Processing: {task_file.name}")

    raw = task_file.read_text(encoding="utf-8", errors="replace")

    # Extract a title (first H1 line, frontmatter title:, or filename)
    title = task_file.stem
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            break
        if re.match(r"^title:\s*", line, re.IGNORECASE):
            title = line.split(":", 1)[1].strip().strip('"').strip("'")
            break

    print(f"    Title: {title}")

    # Run Claude reasoning loop
    plan = _reason_about_task(title, raw)

    # Write plan file
    plan_path = create_plan_file(task_file, plan, dry)

    action = "dry_run" if dry else "plan_created"
    print(f"    >> {action} >> {plan_path.name if plan_path else 'N/A'}")
    print(f"       Priority: {plan['priority']} | Approval: {plan['requires_approval']}")

    return {
        "task_file": task_file.name,
        "title": title,
        "plan_file": plan_path.name if plan_path else None,
        "priority": plan["priority"],
        "requires_approval": plan["requires_approval"],
        "action": action,
    }


# ── Main loop ──────────────────────────────────────────────────────────────────

def scan_inbox(seen: set, dry: bool) -> list[dict]:
    """Scan Inbox for unprocessed .md files and plan each one."""
    results = []
    files = sorted(INBOX.glob("*.md"))

    new_files = [f for f in files if f.name not in seen]

    if not new_files:
        return results

    print(f"\nFound {len(new_files)} new file(s) in Inbox/")

    for task_file in new_files:
        try:
            result = process_inbox_file(task_file, dry)
            results.append(result)
            if not dry:
                seen.add(task_file.name)
        except Exception as e:
            print(f"    [ERROR] Failed to process {task_file.name}: {e}")
            results.append({"task_file": task_file.name, "action": "error", "error": str(e)})

    return results


def print_summary(results: list[dict]):
    if not results:
        return
    print(f"\n{'='*50}")
    print(f"Summary: {len(results)} task(s) planned")
    for r in results:
        status = r.get("action", "?")
        plan = r.get("plan_file", "N/A")
        print(f"  [{status}] {r['task_file']} >> {plan}")
    print(f"{'='*50}")
    print(f"Check Needs_Action/ for the created plan files.")


def main():
    parser = argparse.ArgumentParser(description="Silver Tier — Inbox Planner")
    parser.add_argument("--once",  action="store_true", help="Process Inbox once and exit")
    parser.add_argument("--dry",   action="store_true", help="Preview plans without writing files")
    args = parser.parse_args()

    _load_env()

    if args.dry:
        print("DRY RUN MODE -- no files will be written\n")

    seen = _load_seen() if not args.dry else set()

    if args.once:
        print(f"Scanning {INBOX} ...")
        results = scan_inbox(seen, args.dry)
        if not results:
            print("No new files in Inbox/. Nothing to process.")
        else:
            if not args.dry:
                _save_seen(seen)
            print_summary(results)
        return

    # Watch mode
    print(f"Watching {INBOX} every {POLL_INTERVAL}s ... (Ctrl+C to stop)")
    try:
        while True:
            results = scan_inbox(seen, args.dry)
            if results:
                if not args.dry:
                    _save_seen(seen)
                print_summary(results)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
