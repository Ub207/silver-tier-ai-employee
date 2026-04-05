@echo off
schtasks /create /tn "SilverTier_RunAll" /tr "python D:\silver_tier\run_all.py" /sc onlogon /rl highest /f
if %errorlevel% equ 0 (echo SilverTier_RunAll: OK) else (echo SilverTier_RunAll: FAILED - may need Admin rights)

schtasks /create /tn "SilverTier_LinkedIn" /tr "python D:\silver_tier\linkedin_scheduler.py" /sc daily /st 09:00 /rl highest /f
if %errorlevel% equ 0 (echo SilverTier_LinkedIn: OK) else (echo SilverTier_LinkedIn: FAILED - may need Admin rights)

schtasks /query /tn "SilverTier_RunAll" 2>nul && echo Task verified.
