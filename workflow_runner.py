"""
workflow_runner.py — Silver Tier workflow orchestrator

Scans /Needs_Action, classifies files, creates plans, routes to /Pending_Approval.
Updates Dashboard.md with current state.

Usage:
    python workflow_runner.py          # full scan + process
    python workflow_runner.py --dry    # preview only, no writes
"""

import os
import sys
import io
import re
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# Fix Windows cp1252 encoding issues
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────────────────────

VAULT = Path("silver_tier")
NEEDS_ACTION   = VAULT / "Needs_Action"
PENDING        = VAULT / "Pending_Approval"
PLANS          = VAULT / "Plans"
LI_DRAFTS      = VAULT / "LinkedIn_Drafts"
DASHBOARD      = VAULT / "Dashboard.md"
HANDBOOK       = VAULT / "Company_Handbook.md"

# Ensure folders exist
for folder in [NEEDS_ACTION, PENDING, PLANS, LI_DRAFTS]:
    folder.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter key:value pairs from a markdown file."""
    meta = {}
    if not text.startswith("---"):
        return meta
    lines = text.split("\n")
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def set_frontmatter_status(filepath: Path, new_status: str):
    """Update the `status:` field in a file's frontmatter."""
    text    = filepath.read_text(encoding="utf-8", errors="replace")
    updated = re.sub(r"(^status:\s*)(\S+)", rf"\g<1>{new_status}", text, flags=re.MULTILINE)
    filepath.write_text(updated, encoding="utf-8")


def create_plan(context: str, steps: list[str], output: str, requires_approval: bool,
                reasoning: dict = None) -> Path:
    """Write a Plan .md to the Plans folder and return its path."""
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r'[^\w\-]', '_', context.lower())[:40].strip("_")
    plan_path = PLANS / f"PLAN_{slug}_{ts}.md"

    steps_md  = "\n".join(f"- [ ] {s}" for s in steps)
    approval  = "Yes" if requires_approval else "No"

    # Reasoning section (if AI loop was used)
    reasoning_section = ""
    if reasoning:
        reasoning_section = f"""
## AI Reasoning

### Step 1 — Analysis
{reasoning.get("analysis", "—")}

### Step 2 — Plan Decision
- **Priority:** {reasoning.get("priority", "medium")}
- **Estimated Time:** {reasoning.get("estimated_time", "unknown")}
- **Success Criteria:** {reasoning.get("success_criteria", "—")}

"""

    plan_path.write_text(f"""---
type: plan
context: {context}
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
status: active
priority: {reasoning.get("priority", "medium") if reasoning else "medium"}
requires_approval: {approval}
---

# Plan: {context}
*Created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
{reasoning_section}
## Steps
{steps_md}

## Expected Output
{output}

## Status Tracking
- [ ] Plan created
- [ ] Steps executed
- [ ] Output delivered
- [ ] Moved to Done/

## Notes
- Always confirm before sending any external message
- Update step checkboxes as you progress
""", encoding="utf-8")

    return plan_path


# ── Env loader ────────────────────────────────────────────────────────────────

def _load_env():
    """Load .env key=value pairs into os.environ (skips already-set keys)."""
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ── AI reasoning ──────────────────────────────────────────────────────────────

def _static_draft(sender: str) -> dict:
    """Fallback reply templates when Claude API is unavailable."""
    return {
        "urgent": False,
        "invoice": False,
        "financial_flag": False,
        "option_a": f"Hi {sender}, thanks for reaching out. I've received your message and will get back to you shortly.",
        "option_b": f"Got your message! Give me a bit and I'll sort this out for you.",
        "option_c": f"Hi {sender}, I'm tied up right now but will follow up by [TIME]. Hang tight!",
        "option_d": None,
        "recommendation": "B -- friendly tone works best for most clients",
    }


def _ollama_reasoning_loop(item_type: str, sender: str, content: str) -> dict:
    """
    Local AI reasoning using Ollama (free, no API credits needed).
    Falls back to static defaults if Ollama is unavailable.
    """
    import urllib.request
    import json as json_lib
    
    model = os.environ.get("OLLAMA_MODEL", "llama3.2")
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    
    try:
        # Step 1: Analyze
        prompt1 = f"""You are an AI business assistant. Analyze this {item_type} message:

FROM: {sender}
MESSAGE:
{content[:1500]}

Answer concisely (1-2 sentences each):
1. NEED: What does this person need?
2. URGENCY: How urgent? (low/medium/high/critical) and why?
3. CATEGORY: (inquiry/complaint/invoice/followup/spam/social/other)
4. RISK: What happens if we don't respond within 2 hours?

Format your response clearly with numbered answers."""

        req1 = urllib.request.Request(
            f"{base_url}/api/generate",
            data=json_lib.dumps({"model": model, "prompt": prompt1, "stream": False}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req1, timeout=60) as resp:
            analysis = json_lib.loads(resp.read())["response"]
        
        print(f"    [OLLAMA-1] Analysis done.")

        # Step 2: Plan
        prompt2 = f"""Based on this analysis:

{analysis}

Create a concrete action plan. Reply in EXACTLY this format:

STEP_1: [action]
STEP_2: [action]
STEP_3: [action]
PRIORITY: [low/medium/high/critical]
REQUIRES_APPROVAL: [yes/no]
ESTIMATED_TIME: [e.g. 5 minutes]
SUCCESS_CRITERIA: [one line]"""

        req2 = urllib.request.Request(
            f"{base_url}/api/generate",
            data=json_lib.dumps({"model": model, "prompt": prompt2, "stream": False}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req2, timeout=60) as resp:
            plan_text = json_lib.loads(resp.read())["response"]
        
        print(f"    [OLLAMA-2] Plan generated.")

        # Parse plan
        steps, priority, requires_approval = [], "medium", True
        estimated_time, success_criteria = "5-10 minutes", "Response sent and confirmed"

        for line in plan_text.splitlines():
            line = line.strip()
            if re.match(r"STEP_\d+:", line, re.IGNORECASE):
                steps.append(line.split(":", 1)[1].strip())
            elif line.upper().startswith("PRIORITY:"):
                priority = line.split(":", 1)[1].strip().lower()
            elif line.upper().startswith("REQUIRES_APPROVAL:"):
                requires_approval = "yes" in line.lower()
            elif line.upper().startswith("ESTIMATED_TIME:"):
                estimated_time = line.split(":", 1)[1].strip()
            elif line.upper().startswith("SUCCESS_CRITERIA:"):
                success_criteria = line.split(":", 1)[1].strip()

        if not steps:
            steps = ["Review message", "Draft response", "Get approval", "Send reply"]

        return {
            "analysis":          analysis,
            "plan_steps":        steps,
            "priority":          priority,
            "requires_approval": requires_approval,
            "estimated_time":    estimated_time,
            "success_criteria":  success_criteria,
        }

    except Exception as e:
        print(f"    [OLLAMA] Error: {e} — falling through to next AI provider")
        raise  # Let _reasoning_loop handle the fallback


def _reasoning_loop(item_type: str, sender: str, content: str) -> dict:
    """
    2-step AI reasoning loop:
    Step 1 — Analyze: understand the situation deeply
    Step 2 — Plan: decide concrete steps based on analysis

    Tries Ollama (local) first, then Anthropic, then falls back to defaults.
    """
    # Try Ollama first (free, local)
    ollama_model = os.environ.get("OLLAMA_MODEL", "").strip()
    if ollama_model:
        print(f"    [AI] Using Ollama ({ollama_model})...")
        try:
            return _ollama_reasoning_loop(item_type, sender, content)
        except Exception as e:
            print(f"    [AI] Ollama failed ({e}) — trying Anthropic...")

    # Try Anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print(f"    [AI] No API key — using static defaults")
        return {
            "analysis": "API key not set — manual review needed.",
            "plan_steps": ["Review message manually", "Draft response", "Send after approval"],
            "priority": "medium",
            "requires_approval": True,
            "estimated_time": "unknown",
            "success_criteria": "Response sent and acknowledged",
        }

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # ── Loop Step 1: Analyze ──────────────────────────────────────────────
        analysis_resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": f"""You are an AI business assistant.
Analyze this {item_type} message and answer concisely:

FROM: {sender}
MESSAGE:
{content[:1500]}

Answer these 4 questions (1-2 sentences each):
1. NEED: What does this person need?
2. URGENCY: How urgent? (low/medium/high/critical) and why?
3. CATEGORY: (inquiry/complaint/invoice/followup/spam/social/other)
4. RISK: What happens if we don't respond within 2 hours?"""}]
        ).content[0].text.strip()

        print(f"    [LOOP-1] Analysis done.")

        # ── Loop Step 2: Plan ─────────────────────────────────────────────────
        plan_resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": f"""Based on this analysis of a {item_type} from {sender}:

{analysis_resp}

Create a concrete action plan. Reply in EXACTLY this format:

STEP_1: [action]
STEP_2: [action]
STEP_3: [action]
STEP_4: [action]
STEP_5: [action]
PRIORITY: [low/medium/high/critical]
REQUIRES_APPROVAL: [yes/no]
ESTIMATED_TIME: [e.g. 5 minutes]
SUCCESS_CRITERIA: [one line — how do we know this is done?]"""}]
        ).content[0].text.strip()

        print(f"    [LOOP-2] Plan generated.")

        # ── Parse Step 2 output ───────────────────────────────────────────────
        steps, priority, requires_approval = [], "medium", True
        estimated_time, success_criteria = "5-10 minutes", "Response sent and confirmed"

        for line in plan_resp.splitlines():
            line = line.strip()
            if re.match(r"STEP_\d+:", line, re.IGNORECASE):
                steps.append(line.split(":", 1)[1].strip())
            elif line.upper().startswith("PRIORITY:"):
                priority = line.split(":", 1)[1].strip().lower()
            elif line.upper().startswith("REQUIRES_APPROVAL:"):
                requires_approval = "yes" in line.lower()
            elif line.upper().startswith("ESTIMATED_TIME:"):
                estimated_time = line.split(":", 1)[1].strip()
            elif line.upper().startswith("SUCCESS_CRITERIA:"):
                success_criteria = line.split(":", 1)[1].strip()

        if not steps:
            steps = ["Review message", "Draft response", "Get approval", "Send reply"]

        return {
            "analysis":          analysis_resp,
            "plan_steps":        steps,
            "priority":          priority,
            "requires_approval": requires_approval,
            "estimated_time":    estimated_time,
            "success_criteria":  success_criteria,
        }

    except Exception as e:
        print(f"    [LOOP] Error: {e}")
        return {
            "analysis": f"Reasoning failed: {e}",
            "plan_steps": ["Review manually", "Draft response", "Send after approval"],
            "priority": "medium",
            "requires_approval": True,
            "estimated_time": "unknown",
            "success_criteria": "Task completed",
        }


def _parse_claude_response(text: str, sender: str) -> dict:
    """Parse Claude's structured plain-text response into a dict."""
    def grab(key: str) -> str:
        m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    def grab_bool(key: str) -> bool:
        return grab(key).lower() in ("true", "yes")

    financial_flag = grab_bool("FINANCIAL_FLAG")
    option_d_raw   = grab("OPTION_D")
    option_d       = option_d_raw if (financial_flag and option_d_raw and option_d_raw.upper() != "NONE") else None

    fallback = _static_draft(sender)
    return {
        "urgent":         grab_bool("URGENT"),
        "invoice":        grab_bool("INVOICE"),
        "financial_flag": financial_flag,
        "option_a":       grab("OPTION_A") or fallback["option_a"],
        "option_b":       grab("OPTION_B") or fallback["option_b"],
        "option_c":       grab("OPTION_C") or fallback["option_c"],
        "option_d":       option_d,
        "recommendation": grab("RECOMMENDATION") or "B",
    }


def _ollama_classify_and_draft(sender: str, message_body: str) -> dict:
    """
    Local AI classification using Ollama (free, no API credits needed).
    Falls back to static templates if Ollama is unavailable.
    """
    import urllib.request
    import json as json_lib
    
    model = os.environ.get("OLLAMA_MODEL", "llama3.2")
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    
    try:
        prompt = f"""You are a professional WhatsApp assistant for a Pakistani business.
Analyze the message below and respond in EXACTLY this format (no extra lines):

URGENT: true/false
INVOICE: true/false
FINANCIAL_FLAG: true/false
OPTION_A: [professional reply, max 300 chars]
OPTION_B: [friendly/warm reply, max 300 chars. Use "Bhai" only if sender's tone is informal]
OPTION_C: [defer/buy-time reply with [TIME] placeholder, max 300 chars]
OPTION_D: [escalation/clarification reply if FINANCIAL_FLAG=true, else NONE]
RECOMMENDATION: [A, B, C, or D] -- [one sentence reason]

Rules:
- FINANCIAL_FLAG = true when message involves invoice/payment AND amount is unknown or >= PKR 10,000
- Never fabricate amounts, invoice numbers, or dates
- Keep replies under 300 characters
- Use [TIME] as placeholder for specific times

Message from {sender}:
---
{message_body[:1500]}
---"""

        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=json_lib.dumps({"model": model, "prompt": prompt, "stream": False}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = _parse_claude_response(json_lib.loads(resp.read())["response"], sender)
        
        flags = [k.upper() for k in ("urgent", "invoice", "financial_flag") if result.get(k)]
        print(f"    [OLLAMA] Classification: {', '.join(flags) or 'general inquiry'}")
        return result

    except Exception as e:
        print(f"    [OLLAMA] Error: {e} — falling through to next AI provider")
        raise  # Let _classify_and_draft handle the fallback


def _classify_and_draft(sender: str, message_body: str) -> dict:
    """
    Use AI to classify a WA message and generate contextual reply options.
    Tries Ollama (local) first, then Anthropic, then falls back to static templates.
    """
    # Try Ollama first (free, local)
    ollama_model = os.environ.get("OLLAMA_MODEL", "").strip()
    if ollama_model:
        print(f"    [AI] Using Ollama ({ollama_model}) for classification...")
        try:
            return _ollama_classify_and_draft(sender, message_body)
        except Exception as e:
            print(f"    [AI] Ollama failed ({e}) — trying Anthropic...")

    # Try Anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("    [AI] No API key -- using static reply templates.")
        return _static_draft(sender)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""You are a professional WhatsApp assistant for a Pakistani business.
Analyze the message below and respond in EXACTLY this format (no extra lines):

URGENT: true/false
INVOICE: true/false
FINANCIAL_FLAG: true/false
OPTION_A: [professional reply, max 300 chars]
OPTION_B: [friendly/warm reply, max 300 chars. Use "Bhai" only if sender's tone is informal]
OPTION_C: [defer/buy-time reply with [TIME] placeholder, max 300 chars]
OPTION_D: [escalation/clarification reply if FINANCIAL_FLAG=true, else NONE]
RECOMMENDATION: [A, B, C, or D] -- [one sentence reason]

Rules:
- FINANCIAL_FLAG = true when message involves invoice/payment AND amount is unknown or >= PKR 10,000
- Never fabricate amounts, invoice numbers, or dates
- Keep replies under 300 characters
- Use [TIME] as placeholder for specific times

Message from {sender}:
---
{message_body[:1500]}
---"""

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        result = _parse_claude_response(resp.content[0].text, sender)
        flags = [k.upper() for k in ("urgent", "invoice", "financial_flag") if result.get(k)]
        print(f"    [AI] Classification: {', '.join(flags) or 'general inquiry'}")
        return result

    except Exception as e:
        print(f"    [AI] Claude error: {e} -- using static templates")
        return _static_draft(sender)


# ── Processors ────────────────────────────────────────────────────────────────

def process_whatsapp(filepath: Path, meta: dict, dry: bool) -> dict:
    sender   = meta.get("from", "Unknown")
    priority = meta.get("priority", "normal")
    status   = meta.get("status", "pending")

    if status in ("awaiting_approval", "approved", "done"):
        return {"file": filepath.name, "action": "skipped", "reason": status}

    original = filepath.read_text(encoding="utf-8", errors="replace")

    plan = None
    ai   = {}

    if not dry:
        # ── Reasoning Loop (Step 1+2) ─────────────────────────────────────────
        print(f"    [AI] Running reasoning loop for {sender}...")
        reasoning = _reasoning_loop("WhatsApp", sender, original)

        # ── Classification Loop ───────────────────────────────────────────────
        print(f"    [AI] Classifying + drafting replies...")
        ai = _classify_and_draft(sender, original)

        # Elevate priority from reasoning loop if needed
        r_priority = reasoning.get("priority", "normal")
        if r_priority in ("high", "critical") or ai.get("urgent"):
            priority = r_priority if r_priority in ("high", "critical") else "high"

        flags    = [k.upper() for k in ("urgent", "invoice", "financial_flag") if ai.get(k)]
        flag_str = ", ".join(flags) if flags else "general"

        plan = create_plan(
            context=f"WhatsApp reply to {sender}",
            steps=reasoning.get("plan_steps", [
                f"Analyzed message — classification: {flag_str}",
                "AI generated reply options",
                "Route to Pending_Approval",
                "Human selects reply",
                "Send via WhatsApp",
            ]),
            output=f"Pending_Approval/WA_REPLY_{filepath.name}",
            requires_approval=reasoning.get("requires_approval", True),
            reasoning=reasoning,
        )

        # Financial warning block
        financial_warning = ""
        if ai.get("financial_flag"):
            financial_warning = """\n> [!WARNING]
> **FINANCIAL FLAG**: Invoice/payment message detected.
> Confirm the amount is < PKR 10,000 before approving.
> If >= PKR 10,000, escalate to secondary approval.\n"""

        # Option D block (only for financial flag)
        option_d_block = ""
        if ai.get("option_d"):
            option_d_block = f"\n**Option D — Escalation / Info Request (FINANCIAL_FLAG):**\n> {ai['option_d']}\n"

        approval_path = PENDING / f"WA_REPLY_{filepath.name}"
        approval_path.write_text(f"""---
type: whatsapp_reply
original_file: {filepath.name}
from: {sender}
priority: {priority}
status: awaiting_approval
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
plan: {plan.name}
classification: {flag_str}
financial_flag: {str(ai.get("financial_flag", False)).lower()}
---

## Original Message
{original}

---
{financial_warning}
## AI Classification
| Flag | Detected |
|------|----------|
| URGENT | {ai.get("urgent", False)} |
| INVOICE | {ai.get("invoice", False)} |
| FINANCIAL_FLAG | {ai.get("financial_flag", False)} |

---

## Reply Options

**Option A — Professional:**
> {ai.get("option_a", "")}

**Option B — Friendly (Recommended for repeat clients):**
> {ai.get("option_b", "")}

**Option C — Defer / Buy Time:**
> {ai.get("option_c", "")}
{option_d_block}
---

> **AI Recommendation:** {ai.get("recommendation", "Option B")}

---

## Approval
- [ ] Approved reply: [A / B / C{" / D" if ai.get("option_d") else ""} / Custom]
- [ ] Custom reply text (if applicable):

>

""", encoding="utf-8")

        set_frontmatter_status(filepath, "awaiting_approval")

    return {
        "file": filepath.name,
        "type": "whatsapp",
        "from": sender,
        "priority": priority,
        "action": "routed_to_approval" if not dry else "dry_run",
        "approval_file": f"WA_REPLY_{filepath.name}" if not dry else None,
        "plan": plan.name if plan else None,
        "financial_flag": ai.get("financial_flag", False),
    }


def process_email(filepath: Path, meta: dict, dry: bool) -> dict:
    subject = meta.get("subject", "No Subject")
    sender = meta.get("from", "Unknown")
    status = meta.get("status", "pending")

    if status in ("awaiting_approval", "approved", "done"):
        return {"file": filepath.name, "action": "skipped", "reason": status}

    plan = None
    if not dry:
        original = filepath.read_text(encoding="utf-8", errors="replace")
        print(f"    [AI] Running reasoning loop for email: {subject[:40]}...")
        reasoning = _reasoning_loop("email", sender, original)

        plan = create_plan(
            context=f"Email reply: {subject[:50]}",
            steps=reasoning.get("plan_steps", [
                "Read email content",
                "Draft reply",
                "Route to Pending_Approval",
                "Human approves → send",
            ]),
            output=f"Pending_Approval/EMAIL_REPLY_{filepath.name}",
            requires_approval=reasoning.get("requires_approval", True),
            reasoning=reasoning,
        )
        set_frontmatter_status(filepath, "awaiting_approval")

    return {
        "file": filepath.name,
        "type": "email",
        "from": sender,
        "subject": subject,
        "action": "noted_for_review" if not dry else "dry_run",
        "plan": plan.name if plan else None,
    }


def process_drop(filepath: Path, meta: dict, dry: bool) -> dict:
    status = meta.get("status", "pending")
    if status in ("done", "awaiting_approval"):
        return {"file": filepath.name, "action": "skipped", "reason": status}

    plan = None
    if not dry:
        plan = create_plan(
            context=f"Process dropped task: {filepath.stem}",
            steps=["Read task details", "Identify action owner", "Execute or delegate"],
            output="Completed task or delegated item",
            requires_approval=False,
        )
        set_frontmatter_status(filepath, "awaiting_approval")

    return {
        "file": filepath.name,
        "type": "drop",
        "action": "plan_created" if not dry else "dry_run",
        "plan": plan.name if plan else None,
    }


# ── Dashboard updater ─────────────────────────────────────────────────────────

def update_dashboard(results: list[dict]):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    wa_rows = []
    li_rows = []
    approval_rows = []
    plan_rows = []

    for r in results:
        if r.get("action") == "skipped":
            continue

        t = r.get("type", "unknown")
        if t == "whatsapp":
            wa_rows.append(
                f"| {r['file']} | {r.get('from','—')} | {now} "
                f"| {r.get('priority','—')} | {r.get('action','—')} |"
            )
            if r.get("approval_file"):
                approval_rows.append(
                    f"| {r['approval_file']} | WhatsApp Reply | Select & approve reply option |"
                )
        elif t == "email":
            approval_rows.append(
                f"| {r['file']} | Email | Review and approve reply |"
            )

        if r.get("plan"):
            plan_rows.append(f"| {r['plan']} | {t} | {now} |")

    # LinkedIn personal drafts
    for lf in LI_DRAFTS.glob("LI_*.md"):
        li_rows.append(f"| {lf.name} | — | Draft | {lf.stat().st_mtime:.0f} |")

    # LinkedIn company posts — scan LI_CO_* across drafts + pending + approved
    li_co_rows = []
    for folder, label in [(LI_DRAFTS, "Draft"), (PENDING, "Pending"), (VAULT / "Approved", "Approved")]:
        if folder.exists():
            for lf in folder.glob("LI_CO_*.md"):
                try:
                    text = lf.read_text(encoding="utf-8", errors="ignore")
                    pillar, chars = "—", "—"
                    for line in text.splitlines():
                        if line.startswith("pillar:"):
                            pillar = line.split(":", 1)[1].strip()
                        if line.startswith("characters:"):
                            chars = line.split(":", 1)[1].strip()
                        if pillar != "—" and chars != "—":
                            break
                    mtime = datetime.fromtimestamp(lf.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    li_co_rows.append(f"| {lf.name} | {pillar} | {label} | {chars} | {mtime} |")
                except Exception:
                    li_co_rows.append(f"| {lf.name} | — | {label} | — | — |")

    wa_table    = "\n".join(wa_rows)    if wa_rows    else "| — | — | — | — | No pending items |"
    li_co_table = "\n".join(li_co_rows) if li_co_rows else "| — | — | — | — | No company posts today |"
    li_table    = "\n".join(li_rows)    if li_rows    else "| — | — | — | No drafts today |"
    approval_table = "\n".join(approval_rows) if approval_rows else "| — | — | — |"
    plan_table  = "\n".join(plan_rows)  if plan_rows  else "| — | — | — |"

    pending_approvals = list(PENDING.glob("*.md"))
    pending_count = len(pending_approvals)

    DASHBOARD.write_text(f"""# Dashboard
*Auto-updated by workflow_runner.py — last run: {now}*

---

## Pending WhatsApp Messages
| File | From | Received | Priority | Status |
|------|------|----------|----------|--------|
{wa_table}

---

## LinkedIn Company Posts Today
| File | Pillar | Status | Characters | Created |
|------|--------|--------|------------|---------|
{li_co_table}

---

## LinkedIn Drafts / Posts Today
| File | Topic | Status | Created |
|------|-------|--------|---------|
{li_table}

---

## Pending Approvals ({pending_count} item{"s" if pending_count != 1 else ""})
| File | Type | Action Needed |
|------|------|---------------|
{approval_table}

---

## Recent Plans
| Plan | Context | Created |
|------|---------|---------|
{plan_table}

---

## System Status
| Watcher | Last Run | Status |
|---------|----------|--------|
| WhatsApp Watcher | {now} | workflow_runner |
| Filesystem Watcher | {now} | workflow_runner |

---

*Run `python workflow_runner.py` to refresh.*
""", encoding="utf-8")

    print(f"\nDashboard updated >> {DASHBOARD}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Silver Tier — Workflow Runner")
    parser.add_argument("--dry", action="store_true",
                        help="Preview actions without writing any files")
    args = parser.parse_args()

    _load_env()

    if args.dry:
        print("DRY RUN MODE — no files will be written\n")

    print(f"Scanning {NEEDS_ACTION} ...")
    files = sorted(NEEDS_ACTION.glob("*.md"))

    if not files:
        print("No files in Needs_Action/. Nothing to process.")
        if not args.dry:
            update_dashboard([])
        return

    results = []
    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(text)
        file_type = meta.get("type", "")

        print(f"  [{file_type or 'unknown'}] {fp.name} — status: {meta.get('status','?')}")

        if fp.name.startswith("WA_") or file_type == "whatsapp":
            result = process_whatsapp(fp, meta, args.dry)
        elif fp.name.startswith("EMAIL_") or file_type == "email":
            result = process_email(fp, meta, args.dry)
        else:
            result = process_drop(fp, meta, args.dry)

        results.append(result)
        print(f"    >> {result.get('action','?')}"
              + (f" | plan: {result['plan']}" if result.get("plan") else ""))

    if not args.dry:
        update_dashboard(results)

    print(f"\nDone. {len(results)} file(s) processed.")
    print(f"Check {PENDING}/ for items needing your approval.")


if __name__ == "__main__":
    main()
