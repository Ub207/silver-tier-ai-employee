@echo off
:: setup_scheduler.bat — Register AI Employee Scheduler with Windows Task Scheduler
:: Run this file as Administrator (right-click > Run as administrator)

setlocal

:: ── Config — edit these if your paths differ ───────────────────────────────
set PROJECT_DIR=D:\silver_tier
set SCRIPT=scripts\run_ai_employee.py
set TASK_NAME=SilverTier_AIEmployee
set LOG_DIR=%PROJECT_DIR%\logs

:: Auto-detect Python
for /f "delims=" %%i in ('where python 2^>nul') do (
    set PYTHON=%%i
    goto :found_python
)
echo [ERROR] Python not found in PATH. Install Python 3.10+ and try again.
pause
exit /b 1

:found_python
echo [INFO] Using Python: %PYTHON%

:: ── Create logs directory ──────────────────────────────────────────────────
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: ── Remove existing task if it exists ─────────────────────────────────────
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel% == 0 (
    echo [INFO] Removing existing task: %TASK_NAME%
    schtasks /delete /tn "%TASK_NAME%" /f >nul
)

:: ── Register new task ──────────────────────────────────────────────────────
:: Runs every 5 minutes, starts at logon, runs whether or not user is logged on
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON%\" \"%PROJECT_DIR%\%SCRIPT%\" --once" ^
  /sc MINUTE ^
  /mo 5 ^
  /rl HIGHEST ^
  /f ^
  /ru "%USERNAME%" ^
  /delay 0000:30

if %errorlevel% neq 0 (
    echo [ERROR] Failed to create scheduled task. Make sure you are running as Administrator.
    pause
    exit /b 1
)

echo.
echo [OK] Task registered successfully.
echo      Name     : %TASK_NAME%
echo      Script   : %PROJECT_DIR%\%SCRIPT%
echo      Schedule : Every 5 minutes
echo      Log file : %LOG_DIR%\ai_employee.log
echo.
echo Useful commands:
echo   Check task status : schtasks /query /tn %TASK_NAME% /fo LIST /v
echo   Run manually now  : schtasks /run /tn %TASK_NAME%
echo   Stop task         : schtasks /end /tn %TASK_NAME%
echo   Remove task       : schtasks /delete /tn %TASK_NAME% /f
echo.
pause
