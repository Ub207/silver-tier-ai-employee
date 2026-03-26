<p align="center">
  <img src="https://img.shields.io/badge/Tier-Silver-C0C0C0?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Status-Production-brightgreen?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Python-3.9+-yellow?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Claude-Opus_4-FF6B35?style=for-the-badge&logo=anthropic&logoColor=white" />
</p>

<h1 align="center">AI Employee - Silver Tier</h1>
<p align="center"><strong>Email automation, LinkedIn posting, and WhatsApp monitoring with human-in-the-loop approval.</strong></p>

---

## What Silver Tier Adds

Building on Bronze Tier's core agent loop, Silver introduces **real-world integrations**:

| Feature | Description |
|---------|------------|
| **Gmail OAuth** | Automated email monitoring, drafting, and sending |
| **LinkedIn Personal** | AI-drafted posts with approval workflow |
| **LinkedIn Company** | Company page posts with image support |
| **WhatsApp** | Message monitoring via WhatsApp Web |
| **Obsidian Vault** | Visual GUI for reviewing and approving actions |
| **Browser Automation** | Navigate, click, fill forms, take screenshots |

---

## MCP Server Integrations

```
  email ────────── Gmail: send, read, search, draft (OAuth2)
  linkedin ─────── Personal & Company page posts
  filesystem ──── Vault read/write/search
  browser ──────── Web automation (navigate, click, fill)
```

---

## Approval Workflow

```
Email/WhatsApp arrives
        │
        ▼
Watcher creates Needs_Action/*.md
        │
        ▼
inbox_planner.py creates Plan
        │
        ▼
Draft goes to Pending_Approval/
        │
        ▼
Human reviews in Obsidian ──► Approve or Reject
        │
        ▼
approval_executor.py sends via MCP ──► Done/
```

## Safety Rules

- **Human approves** every outbound message
- **Never auto-send** emails, posts, or messages
- **Rate limited**: Max 2 LinkedIn posts/week
- **Audit trail**: Every action logged

---

## Vault Structure

```
silver_tier/
├── Dashboard.md              # Real-time status
├── Company_Handbook.md       # Rules of engagement
├── Needs_Action/             # Incoming items
├── Plans/                    # Action plans
├── Pending_Approval/         # Awaiting human decision
├── Approved/                 # Ready to execute
├── Done/                     # Completed
├── LinkedIn_Drafts/          # Social content
└── Logs/                     # Audit trail
```

---

## Quick Start

```bash
git clone https://github.com/Ub207/silver-tier-ai-employee.git
cd silver-tier-ai-employee
pip install -r requirements.txt
cp .env.example .env  # Add Gmail, LinkedIn credentials
python workflow_runner.py
```

---

<p align="center">
  <strong>Built by <a href="https://github.com/Ub207">Ubaid ur Rahman</a></strong><br/>
  AI Automation Consulting | <a href="mailto:usmanubaidurrehman@gmail.com">Hire Me</a>
</p>
