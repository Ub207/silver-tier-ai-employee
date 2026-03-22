/**
 * ecosystem.config.js — PM2 process manager for Silver Tier watchers
 *
 * Install PM2 (one-time):
 *   npm install -g pm2
 *
 * Start all watchers:
 *   pm2 start ecosystem.config.js
 *
 * Other commands:
 *   pm2 list               — see all processes
 *   pm2 logs               — tail all logs
 *   pm2 logs whatsapp-watcher  — specific process logs
 *   pm2 restart all        — restart everything
 *   pm2 stop all           — stop all
 *   pm2 save               — persist processes across reboots
 *   pm2 startup            — auto-start on system boot (run the command it prints)
 */

module.exports = {
  apps: [
    {
      name: "whatsapp-watcher",
      script: "python",
      args: "whatsapp_watcher.py --vault silver_tier --interval 180",
      interpreter: "none",
      watch: false,
      autorestart: true,
      restart_delay: 10000,       // wait 10s before restarting on crash
      max_restarts: 10,
      log_file: "logs/whatsapp-watcher.log",
      error_file: "logs/whatsapp-watcher-error.log",
      out_file: "logs/whatsapp-watcher-out.log",
      env: {
        PYTHONIOENCODING: "utf-8",
      },
    },
    {
      name: "workflow-runner",
      script: "python",
      args: "workflow_runner.py",
      interpreter: "none",
      // Run workflow_runner on a schedule via cron_restart
      // Restarts (= runs) every 5 minutes
      cron_restart: "*/5 * * * *",
      autorestart: false,
      watch: false,
      log_file: "logs/workflow-runner.log",
      error_file: "logs/workflow-runner-error.log",
      out_file: "logs/workflow-runner-out.log",
      env: {
        PYTHONIOENCODING: "utf-8",
      },
    },
    {
      name: "filesystem-watcher",
      script: "python",
      args: "filesystem_watcher.py --vault silver_tier",
      interpreter: "none",
      watch: false,
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      log_file: "logs/filesystem-watcher.log",
      error_file: "logs/filesystem-watcher-error.log",
      out_file: "logs/filesystem-watcher-out.log",
      env: {
        PYTHONIOENCODING: "utf-8",
      },
    },
    {
      name: "gmail-imap-watcher",
      script: "python",
      args: "gmail_imap_watcher.py",
      interpreter: "none",
      watch: false,
      autorestart: true,
      restart_delay: 10000,
      max_restarts: 5,
      log_file: "logs/gmail-imap-watcher.log",
      error_file: "logs/gmail-imap-watcher-error.log",
      out_file: "logs/gmail-imap-watcher-out.log",
      env: {
        PYTHONIOENCODING: "utf-8",
      },
    },
    {
      name: "gmail-watcher",
      script: "python",
      args: "gmail_watcher.py --vault silver_tier",
      interpreter: "none",
      watch: false,
      autorestart: true,
      restart_delay: 10000,
      max_restarts: 5,
      log_file: "logs/gmail-watcher.log",
      error_file: "logs/gmail-watcher-error.log",
      out_file: "logs/gmail-watcher-out.log",
      env: {
        PYTHONIOENCODING: "utf-8",
      },
    },
    {
      name: "auto-approver",
      script: "python",
      args: "auto_approver.py",
      interpreter: "none",
      watch: false,
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      log_file: "logs/auto-approver.log",
      error_file: "logs/auto-approver-error.log",
      out_file: "logs/auto-approver-out.log",
      env: {
        PYTHONIOENCODING: "utf-8",
      },
    },
    {
      name: "approval-executor",
      script: "python",
      args: "approval_executor.py",
      interpreter: "none",
      watch: false,
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      log_file: "logs/approval-executor.log",
      error_file: "logs/approval-executor-error.log",
      out_file: "logs/approval-executor-out.log",
      env: {
        PYTHONIOENCODING: "utf-8",
      },
    },
    {
      name: "inbox-planner",
      script: "python",
      args: "inbox_planner.py",
      interpreter: "none",
      watch: false,
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      log_file: "logs/inbox-planner.log",
      error_file: "logs/inbox-planner-error.log",
      out_file: "logs/inbox-planner-out.log",
      env: {
        PYTHONIOENCODING: "utf-8",
      },
    },
    {
      name: "linkedin-scheduler",
      script: "python",
      args: "linkedin_scheduler.py",
      interpreter: "none",
      // Run linkedin_scheduler daily at 09:00 AM
      cron_restart: "0 9 * * *",
      autorestart: false,
      watch: false,
      log_file: "logs/linkedin-scheduler.log",
      error_file: "logs/linkedin-scheduler-error.log",
      out_file: "logs/linkedin-scheduler-out.log",
      env: {
        PYTHONIOENCODING: "utf-8",
      },
    },
  ],
};
