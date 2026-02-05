@echo off
cd /d "%~dp0"
echo Pushing to GitHub...
"C:\Program Files\Git\cmd\git.exe" push -u origin main
if %errorlevel% neq 0 (
    echo Push failed.
    pause
    exit /b %errorlevel%
)
echo Push success!
pause
