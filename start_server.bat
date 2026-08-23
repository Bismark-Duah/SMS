@echo off
TITLE SchoolManager Enterprise Launcher
COLOR 0A
CLS

ECHO =========================================================================
ECHO           SCHOOLMANAGER ENTERPRISE SYSTEM LAUNCHER                       
ECHO =========================================================================
ECHO  [1/2] Starting Local School Server on http://127.0.0.1:8000 ...
ECHO  [2/2] Opening Web Browser to School Dashboard ...
ECHO =========================================================================
ECHO.

cd /d "%~dp0"

START "" http://127.0.0.1:8000/assets/dashboard.html

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

PAUSE
