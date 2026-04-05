# Silver Tier AI Employee

**Hackathon Tier: Silver — Functional Assistant (20-30 hrs)**

A 24/7 autonomous AI employee that monitors Gmail, WhatsApp, and your filesystem, reasons about each incoming item, drafts replies, posts to LinkedIn, and routes everything through a human-in-the-loop approval workflow — all stored in an Obsidian vault you can browse like a live dashboard.

---

## Architecture

```
Gmail / WhatsApp / Files
        |
        v  (Watchers — lightweight Python scripts)
 Needs_Action/*.md
        |
        v  (workflow_runner.py + Ollama / Claude API)
 Plans/*.md  +  Pending_Approval/*.md
        |
        v  (You review in Obsidian, move to Approved/)
   Approved/*.md
        |
        v  (approval_executor.py + MCP servers)
Send email / Post LinkedIn  -->  Done/
```

**Brain:** `workflow_runner.py` — 2-step AI reasoning loop (Analyze → Plan) using Ollama locally, with Anthropic Claude as fallback.

**Memory / GUI:** Obsidian vault at `silver_tier/` — open it to see a live dashboard of pending items, plans, and approval queues.

**Watchers (Senses):**
- `gmail_watcher.py` — IMAP polling every 3 minutes
- `whatsapp_watcher.py` — Playwright automation of WhatsApp Web
- `filesystem_watcher.py` — watchdog monitors the `Inbox/` drop folder

**MCP Servers (Hands):**
- `email_mcp_server.py` — send / list / archive email via SMTP
- `linkedin_mcp.py` — company + personal LinkedIn posting via Playwright

**Stop Hook:** `stop_hook.py` — Ralph Wiggum loop that blocks Claude from exiting while items remain in `Pending_Approval/`

---

## Quick Start

```bash
# 1. Clone and enter project
git clone https://github.com/Ub207/silver-tier-ai-employee.git
cd silver-tier-ai-employee

# 2. Install Python dependencies
pip install -r requirements.txt   # or: pip install playwright watchdog anthropic

# 3. Copy and fill in credentials
cp .env.example .env
# Edit .env with your API keys (see Setup section below)

# 4. Install Playwright browsers (for WhatsApp + LinkedIn)
playwright install chromium

# 5. (Optional) Install Ollama for free local AI
# https://ollama.com/download/windows
ollama pull llama3.2:1b

# 6. Launch everything
python run_all.py
```

---

## Setup

### Required Credentials (`.env`)

| Variable | Where to Get |
|----------|-------------|
| `ANTHROPIC_API_KEY` | console.anthropic.com/settings/keys |
| `EMAIL_ADDRESS` | Your Gmail address |
| `EMAIL_APP_PASSWORD` | myaccount.google.com/apppasswords (enable 2FA first) |
| `LINKEDIN_COMPANY_SLUG` | Your LinkedIn company page URL slug |

### Gmail IMAP Setup
1. Enable 2-Factor Authentication on your Google account
2. Go to myaccount.google.com/apppasswords
3. Create an App Password for "Mail"
4. Set `EMAIL_APP_PASSWORD` in `.env`

### WhatsApp Setup (one-time)
```bash
python whatsapp_watcher.py --setup
# Scan the QR code with your phone
# Session is saved to silver_tier/whatsapp_session/ (never committed)
```

### LinkedIn Setup (one-time)
```bash
python linkedin_company_mcp.py --setup
# Log in manually in the browser window that opens
# Session saved to silver_tier/linkedin_session/ (never committed)
```

### Windows Task Scheduler (auto-start on boot)
```bash
setup_task_scheduler.bat
```

---

## Vault Structure (Obsidian)

```
silver_tier/
├── Dashboard.md          # Live status — auto-updated every 5 min
├── Company_Handbook.md   # Rules: tone, approval thresholds, limits
├── Business_Goals.md     # Q1 KPIs and targets
├── Approval_Log.md       # Audit trail of every decision
├── Needs_Action/         # Watchers write here
├── Plans/                # AI-generated action plans (PLAN_*.md)
├── Pending_Approval/     # Awaiting your review
├── Approved/             # You moved it here → executor sends
├── Rejected/             # Rejected with reason
├── Done/                 # Completed
├── LinkedIn_Drafts/      # LI_CO_* company, LI_PERSONAL_* personal
├── Briefings/            # Weekly CEO Briefings (generated Sundays)
└── Inbox/                # Drop-zone: drag any file to trigger processing
```

---

## Key Scripts

| Script | Purpose | Run |
|--------|---------|-----|
| `run_all.py` | Master launcher — all watchers + workflow loop | `python run_all.py` |
| `workflow_runner.py` | Scan Needs_Action, reason, create plans + approval drafts | `python workflow_runner.py` |
| `approval_executor.py` | Watch Approved/, execute actions (email SMTP, LinkedIn) | `python approval_executor.py` |
| `ceo_briefing.py` | Generate weekly Monday Morning CEO Briefing | `python ceo_briefing.py` |
| `cleanup_plans.py` | Archive old plans and stale emails | `python cleanup_plans.py --execute` |
| `linkedin_scheduler.py` | Daily LinkedIn post scheduler | auto-started by run_all.py |

---

## Silver Tier Features

1. **3 Watchers** — Gmail (IMAP), WhatsApp (Playwright), Filesystem (watchdog)
2. **LinkedIn Automation** — company page + personal profile drafts, max 2/week enforced, human always clicks Post
3. **AI Reasoning Loop** — 2-step Ollama/Claude loop: Analyze → Plan → creates `PLAN_*.md`
4. **2 MCP Servers** — `email_mcp_server.py` + `linkedin_mcp.py` registered in `.mcp.json`
5. **HITL Approval Workflow** — every sensitive action goes through `Pending_Approval/` → `Approved/` before execution
6. **Task Scheduler** — `setup_task_scheduler.bat` registers watchers and workflow loop on Windows startup
7. **Agent Skills** — 15 Claude Code skills in `.claude/skills/` covering plans, replies, approvals, LinkedIn, WhatsApp
8. **Ralph Wiggum Stop Hook** — keeps Claude working until `Pending_Approval/` is empty
9. **CEO Briefing** — weekly `Briefings/` report: revenue, completed tasks, bottlenecks, cost suggestions

---

## Security

### Credential Handling
- All secrets stored in `.env` file — **never committed** (in `.gitignore`)
- Gmail credentials: App Password only (no account password stored)
- WhatsApp + LinkedIn sessions: stored in local browser profile folders — **excluded from git** (in `.gitignore`)
- OAuth tokens (`credentials.json`, `token.json`): in `.gitignore`

### Human-in-the-Loop Safeguards
All sensitive actions require explicit human approval before execution:
- WhatsApp replies — always require approval
- Email to clients — require approval
- LinkedIn posts — always require approval (human clicks Post in browser)
- Financial amounts > PKR 10,000 — secondary approval required

### Permission Boundaries
| Action | Auto-Approve | Always Requires Human |
|--------|-------------|----------------------|
| Create drafts / plans / files | Yes | — |
| Email replies | No | Always |
| WhatsApp replies | No | Always |
| LinkedIn posts | No | Always |
| Financial > PKR 10,000 | No | Always + escalation |

### Audit Logging
Every executed action is appended to `silver_tier/Approval_Log.md` with timestamp, type, actor, result.

---

## How Approval Works (HITL Flow)

```
[Email arrives]
  → gmail_watcher.py writes EMAIL_abc.md to Needs_Action/

[workflow_runner.py — every 5 min]
  → reads EMAIL_abc.md
  → Ollama 2-step reasoning: Analyze → Plan
  → creates Plans/PLAN_email_reply_abc.md
  → writes Pending_Approval/EMAIL_REPLY_abc.md  (3 reply options: A/B/C)
  → sets status: awaiting_approval on original

[You open Obsidian]
  → read EMAIL_REPLY_abc.md
  → tick Option A/B/C
  → move file to Approved/

[approval_executor.py]
  → detects Approved/EMAIL_REPLY_abc.md
  → sends reply via SMTP
  → appends to Approval_Log.md
  → moves to Done/
```

---

## Agent Skills (`.claude/skills/`)

| Skill | Purpose |
|-------|---------|
| `plan-creator.md` | Creates PLAN_*.md files |
| `reply-drafter.md` | Drafts email/WhatsApp replies |
| `approval-handler.md` | Processes approval decisions |
| `linkedin-company-poster/` | Drafts + posts to company LinkedIn page |
| `linkedin-personal-poster/` | Drafts + posts to personal profile |
| `whatsapp-processor.md` | Classifies + routes WhatsApp messages |
| `human-approval/` | Manages human-in-the-loop decisions |
| `vault-file-manager/` | Vault read/write/move operations |
| `gmail-send/` | Sends email via MCP |

---

## Tier Declaration

**Silver Tier — Functional Assistant**

All 8 Silver Tier requirements from the hackathon specification are implemented and working.
