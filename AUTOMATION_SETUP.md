# 🚀 Silver Tier — Full Automation Setup Guide

**Last Updated:** March 9, 2026

This guide walks you through setting up **complete automation** for emails, WhatsApp, and LinkedIn.

---

## 📋 Quick Start (5 Minutes)

### Step 1: Install Ollama (Free Local AI)

**Why?** Anthropic API credits khatam ho gaye hain. Ollama free hai aur local chalta hai.

1. **Download:** https://ollama.com/download/windows
2. **Install:** Run `OllamaSetup.exe`
3. **Pull Model:** Open PowerShell/CMD:
   ```bash
   ollama pull llama3.2
   ```

### Step 2: Configure .env File

```bash
# .env file (already exists — edit it)

# Ollama (Local AI - FREE)
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434

# Gmail (for reading emails)
EMAIL_ADDRESS=you@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Email Sender (for auto-reply)
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
```

**Get Gmail App Password:**
1. Go to https://myaccount.google.com/apppasswords
2. Enable 2FA if not already
3. Create App Password → Copy → Paste in `.env`

### Step 3: Run Full Automation

```bash
# Start everything (Gmail + Auto-Approve + Auto-Send)
python full_auto_mode.py

# Or run individual components:
python full_auto_mode.py --email      # Gmail automation only
python full_auto_mode.py --whatsapp   # WhatsApp monitoring only
python full_auto_mode.py --linkedin   # LinkedIn monitoring only
python full_auto_mode.py --once       # Process once and exit
```

---

## 🤖 What's Automated vs Manual

| Task | Status | Notes |
|------|--------|-------|
| **Gmail Reading** | ✅ Fully Automated | Polls every 3 min |
| **Email Classification** | ✅ Automated (Ollama) | AI classifies urgency |
| **Email Reply (Non-Financial)** | ✅ Auto-Send | Generic replies sent automatically |
| **Email Reply (Financial)** | ⚠️ Human Approval | PKR 10,000+ requires approval |
| **WhatsApp Detection** | ✅ Fully Automated | Playwright monitors WA Web |
| **WhatsApp Reply Draft** | ✅ Automated (Ollama) | 3 reply options generated |
| **WhatsApp Reply Send** | ⚠️ Human Click | Must click Send in WA Web |
| **LinkedIn Draft** | ✅ Automated | Creates posts from Business_Goals.md |
| **LinkedIn Post** | ⚠️ Human Approval | Must approve before posting |
| **Dashboard Update** | ✅ Fully Automated | Real-time status |

---

## 📁 Automation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     SILVER TIER AUTOMATION                      │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Gmail      │     │  WhatsApp    │     │  LinkedIn    │
│   Watcher    │     │  Watcher     │     │  Scheduler   │
│  (3 min)     │     │  (Playwright)│     │  (Daily)     │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌──────────────────────────────────────────────────────────────┐
│                   Needs_Action/ Folder                        │
│   EMAIL_*.md  |  WA_*.md  |  LI_*.md  |  DROP_*.md           │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│              workflow_runner.py + Ollama AI                   │
│   • Classifies urgency                                        │
│   • Generates reply options                                   │
│   • Creates Plan.md                                           │
└──────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐
    │  AUTO-APPROVE   │         │  HUMAN REQUIRED │
    │  (Non-Financial)│         │  (Financial/WA) │
    └────────┬────────┘         └────────┬────────┘
             │                           │
             ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐
    │   Approved/     │         │ Pending_Approval│
    │   (Auto-Send)   │         │  (Wait for user)│
    └────────┬────────┘         └────────┬────────┘
             │                           │
             ▼                           ▼
    ┌─────────────────┐         ┌─────────────────┐
    │   Done/         │         │   User Approves │
    │   (Archive)     │         │   → Approved/   │
    └─────────────────┘         └─────────────────┘
```

---

## 🔧 Individual Components

### 1. Gmail Automation

```bash
# Run Gmail watcher only
python gmail_watcher.py

# Or use full automation
python full_auto_mode.py --email
```

**What it does:**
- Polls Gmail every 3 minutes via IMAP
- Creates `EMAIL_*.md` files in `Needs_Action/`
- Marks emails as "seen" to avoid duplicates

---

### 2. WhatsApp Automation

```bash
# First-time setup (QR scan)
python whatsapp_watcher.py --setup

# Run watcher (continuous monitoring)
python whatsapp_watcher.py
```

**What it does:**
- Opens WhatsApp Web in browser
- Monitors for keywords: `urgent`, `invoice`, `payment`, `help`, `asap`, `bhai`
- Creates `WA_*.md` files in `Needs_Action/`
- Session saved in `silver_tier/whatsapp_session/`

---

### 3. LinkedIn Automation

```bash
# Company Page
python linkedin_company_mcp.py

# Personal Profile
python linkedin_personal_mcp.py
```

**What it does:**
- Reads `Business_Goals.md` for content pillars
- Creates drafts in `LinkedIn_Drafts/`
- Enforces 2 posts/week limit
- Opens browser for final "Post" click

---

### 4. Workflow Runner (AI Processing)

```bash
# Process all files in Needs_Action/
python workflow_runner.py

# Dry run (preview only)
python workflow_runner.py --dry
```

**What it does:**
- Reads files from `Needs_Action/`
- Runs Ollama AI reasoning loop
- Creates `Plan_*.md` in `Plans/`
- Routes to `Pending_Approval/` or `Approved/`

---

### 5. Auto Approver

```bash
# Continuous watch mode
python auto_approver.py

# Process once
python auto_approver.py --once

# Preview decisions
python auto_approver.py --report
```

**What it does:**
- Scans `Pending_Approval/`
- **Auto-Archive:** Newsletters, promotions, no-reply senders
- **Auto-Approve:** Low-risk generic inquiries
- **Human Review:** Financial, urgent, WA replies, LinkedIn posts

---

### 6. Approval Executor

```bash
# Execute approved actions
python approval_executor.py

# Dry run (preview)
python approval_executor.py --dry
```

**What it does:**
- Monitors `Approved/` folder
- **Email:** Sends via SMTP
- **LinkedIn:** Runs MCP script → opens browser
- **WhatsApp:** Logs reply for manual send
- Moves completed tasks to `Done/`

---

## 🛡️ Safety Rules (NEVER Bypassed)

| Rule | Enforcement |
|------|-------------|
| **Financial Flag (PKR 10,000+)** | ❌ Always requires human approval |
| **High/Critical Priority** | ❌ Always requires human approval |
| **WhatsApp Replies** | ⚠️ Always requires human click (no business API) |
| **LinkedIn Posts** | ⚠️ Always requires human approval before posting |
| **Email to Unknown Senders** | ⚠️ Always requires human review |

---

## 📊 Monitoring & Logs

### Dashboard

```bash
# View real-time status
cat silver_tier/Dashboard.md
```

### Logs

```
logs/
├── full_auto_20260309.log    # Full automation log
├── whatsapp_watcher.log       # WhatsApp activity
└── approval_executor.log      # Execution results
```

### Approval Log

```bash
# View approval decisions
cat silver_tier/Approval_Log.md
```

---

## 🚨 Troubleshooting

### Ollama Not Working

```bash
# Check if Ollama is running
ollama list

# If not installed, download from:
# https://ollama.com/download/windows

# Test model
ollama run llama3.2 "Hello"
```

### Gmail Auth Failed

```bash
# Check .env file
cat .env | grep EMAIL

# Verify App Password (not regular password)
# Get new one: https://myaccount.google.com/apppasswords
```

### WhatsApp Watcher Crashes

```bash
# Kill stale processes
taskkill /F /IM chrome.exe

# Delete session locks
rm -rf silver_tier/whatsapp_session/Default/Lock*

# Re-run setup
python whatsapp_watcher.py --setup
```

### LinkedIn Session Expired

```bash
# Delete old session
rm -rf silver_tier/linkedin_session/

# Re-login
python linkedin_company_mcp.py
# or
python linkedin_personal_mcp.py
```

---

## 📈 Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Gmail poll interval | 3 min | ✅ 3 min |
| WhatsApp detection | < 5 min | ✅ ~3 min |
| Email auto-reply | < 1 hour | ✅ Instant |
| LinkedIn posts/week | 2 | ✅ Enforced |
| Financial flag accuracy | 100% | ✅ Rule-based |

---

## 🎯 Next Steps

1. **Install Ollama** (if not already)
   ```bash
   # Download: https://ollama.com/download/windows
   ollama pull llama3.2
   ```

2. **Update .env file**
   ```bash
   OLLAMA_MODEL=llama3.2
   EMAIL_ADDRESS=you@gmail.com
   EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
   ```

3. **Run Full Automation**
   ```bash
   python full_auto_mode.py
   ```

4. **Monitor Dashboard**
   ```bash
   # Open in Obsidian or any markdown viewer
   silver_tier/Dashboard.md
   ```

---

## 📞 Support

- **Documentation:** `Personal AI Employee Hackathon 0.md`
- **Company Handbook:** `silver_tier/Company_Handbook.md`
- **Business Goals:** `silver_tier/Business_Goals.md`

---

**Happy Automating! 🚀**
