@echo off
cd /d "%~dp0"
echo Adding new files (AI Core)...
"C:\Program Files\Git\cmd\git.exe" add .
echo Committing...
"C:\Program Files\Git\cmd\git.exe" commit -m "Add AI Core: Model, Preprocessing, and Brain"
echo Pushing...
"C:\Program Files\Git\cmd\git.exe" push
if %errorlevel% neq 0 (
    echo Push failed.
    pause
    exit /b %errorlevel%
)
echo Update Success!
pause
