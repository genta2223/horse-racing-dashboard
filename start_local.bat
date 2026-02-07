@echo off
REM JRA Automated Betting System - Local Startup Script
REM ====================================================
REM Double-click this file to start the system.
REM To run at Windows startup, add a shortcut to:
REM   shell:startup

cd /d "%~dp0"
echo Starting JRA Betting System...
echo.

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the local runner
python run_local.py

pause
