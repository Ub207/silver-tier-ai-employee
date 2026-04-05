@echo off
:: Silver Tier -- Windows Task Scheduler Setup
:: Run this ONCE as Administrator to auto-start on login.
::
:: This creates two scheduled tasks:
::   1. SilverTier_RunAll  -- starts run_all.py at login (runs continuously)
::   2. SilverTier_LinkedIn -- runs LinkedIn scheduler daily at 9:00 AM
::
:: To remove tasks:
::   schtasks /delete /tn "SilverTier_RunAll" /f
::   schtasks /delete /tn "SilverTier_LinkedIn" /f

echo Silver Tier -- Task Scheduler Setup
echo ======================================

:: Check admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Run this script as Administrator.
    echo Right-click >> Run as administrator
    pause
    exit /b 1
)

:: Task 1: run_all.py on login (continuous loop: WA watcher + workflow runner)
echo Creating task: SilverTier_RunAll (on login)...
schtasks /create ^
  /tn "SilverTier_RunAll" ^
  /tr "python D:\silver_tier\run_all.py" ^
  /sc onlogon ^
  /rl highest ^
  /f

if %errorlevel% equ 0 (
    echo   OK: SilverTier_RunAll created.
) else (
    echo   WARNING: Could not create SilverTier_RunAll.
)

:: Task 2: linkedin_scheduler.py daily at 09:00
echo Creating task: SilverTier_LinkedIn (daily 09:00)...
schtasks /create ^
  /tn "SilverTier_LinkedIn" ^
  /tr "python D:\silver_tier\linkedin_scheduler.py" ^
  /sc daily ^
  /st 09:00 ^
  /rl highest ^
  /f

if %errorlevel% equ 0 (
    echo   OK: SilverTier_LinkedIn created.
) else (
    echo   WARNING: Could not create SilverTier_LinkedIn.
)

echo.
echo Done! Tasks will run automatically.
echo Run 'schtasks /query /tn "SilverTier_RunAll"' to verify.
echo.
pause
