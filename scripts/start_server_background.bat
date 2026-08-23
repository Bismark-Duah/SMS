@echo off
REM ================================================================
REM SMS Backend Auto-Start Launcher Script
REM Starts FastAPI backend server on 0.0.0.0:8000
REM ================================================================

cd /d "%~dp0\.."

if not exist logs mkdir logs

echo Starting SMS FastAPI Backend Server... >> logs\server_startup.log
date /t >> logs\server_startup.log
time /t >> logs\server_startup.log

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 >> logs\server.log 2>&1
