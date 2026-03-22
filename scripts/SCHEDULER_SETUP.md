# AI Employee Scheduler — Setup Guide

## Script: `scripts/run_ai_employee.py`

Each cycle:
1. Checks `vault/Inbox/` for new `.md` task files
2. Runs `inbox_planner.py --once` → creates `Plan_*.md` in `Needs_Action/`
3. Runs `workflow_runner.py` → routes plans to `Pending_Approval/`
4. Logs everything to `logs/ai_employee.log`

---

## Quick Test (run once manually)

```bash
cd D:/silver_tier
python scripts/run_ai_employee.py --once
```

Dry run (no files written):
```bash
python scripts/run_ai_employee.py --once --dry
```

Run continuously in terminal (Ctrl+C to stop):
```bash
python scripts/run_ai_employee.py
```

Custom interval (e.g. every 2 minutes):
```bash
python scripts/run_ai_employee.py --interval 120
```

---

## Windows — Task Scheduler (Recommended)

### Option A: Automated setup (run once)

1. Right-click `scripts/setup_scheduler.bat`
2. Click **Run as administrator**
3. Done — task runs every 5 minutes automatically

Verify it was registered:
```
schtasks /query /tn SilverTier_AIEmployee /fo LIST /v
```

Trigger it manually right now:
```
schtasks /run /tn SilverTier_AIEmployee
```

Remove it:
```
schtasks /delete /tn SilverTier_AIEmployee /f
```

---

### Option B: Manual Task Scheduler setup (GUI)

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Task** (not Basic Task — you need full control)

**General tab:**
- Name: `SilverTier_AIEmployee`
- Run whether user is logged on or not: checked
- Run with highest privileges: checked

**Triggers tab:**
- New trigger → **On a schedule**
- Settings: **Daily**, repeat every **5 minutes** for **1 day**
- Begin: today, any time
- Enabled: checked

**Actions tab:**
- New action → **Start a program**
- Program/script: `C:\Path\To\python.exe`
  *(find yours: open CMD, run `where python`)*
- Add arguments: `D:\silver_tier\scripts\run_ai_employee.py --once`
- Start in: `D:\silver_tier`

**Settings tab:**
- If the task is already running: **Stop the existing instance**
- Run task as soon as possible after a scheduled start is missed: checked

3. Click **OK**, enter your Windows password when prompted.

---

### Option C: PM2 (if Node.js is installed)

Add to `ecosystem.config.js`:

```js
{
  name: "ai-employee-scheduler",
  script: "python",
  args: "scripts/run_ai_employee.py",
  interpreter: "none",
  watch: false,
  autorestart: true,
  restart_delay: 5000,
  max_restarts: 20,
  log_file: "logs/ai-employee-scheduler.log",
  env: { PYTHONIOENCODING: "utf-8" },
},
```

Then:
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup     # follow the printed command to auto-start on boot
```

---

## Linux / Mac — Cron Job

Open crontab:
```bash
crontab -e
```

Add this line (runs every 5 minutes):
```
*/5 * * * * cd /path/to/silver_tier && /usr/bin/python3 scripts/run_ai_employee.py --once >> logs/ai_employee_cron.log 2>&1
```

Find your Python path:
```bash
which python3
```

View cron logs:
```bash
tail -f /path/to/silver_tier/logs/ai_employee_cron.log
```

Remove the cron job:
```bash
crontab -e   # delete the line and save
```

---

## Log Files

| File | Contents |
|------|----------|
| `logs/ai_employee.log` | Main scheduler log (cycle summaries) |
| `logs/inbox_planner.log` | inbox_planner.py output per run |
| `logs/workflow_runner.log` | workflow_runner.py output per run |

Tail all logs at once:
```bash
# Windows PowerShell
Get-Content logs\ai_employee.log -Wait -Tail 30

# Linux/Mac
tail -f logs/ai_employee.log
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Task not running | Check Task Scheduler > History tab for error codes |
| `python not found` | Use full Python path in the task action |
| Plans not created | Check `logs/inbox_planner.log` for errors |
| No ANTHROPIC_API_KEY | Plans use default structure (still works, no Claude reasoning) |
| Script times out | Increase timeout in `run_script()` — default is 120s |
