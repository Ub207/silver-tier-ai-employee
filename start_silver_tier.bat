@echo off
:: Silver Tier — Auto-start script
:: This file starts all PM2 watchers on Windows boot.
::
:: To enable auto-start on boot (run ONCE as Administrator):
::   schtasks /create /tn "SilverTier" /tr "D:\silver_tier\start_silver_tier.bat" /sc onlogon /rl highest /f
::
:: To disable:
::   schtasks /delete /tn "SilverTier" /f

echo Starting Silver Tier AI Employee...

:: Restore all saved PM2 processes
pm2 resurrect

:: Give processes 3 seconds to start
timeout /t 3 /nobreak >nul

:: Show status
pm2 list

echo Silver Tier is running.
