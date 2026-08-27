@echo off
TITLE EduManage360 - School Enterprise Management System
COLOR 0A
CLS

ECHO =========================================================================
ECHO           EduManage360 - Enterprise School Management System             
ECHO                   100% Offline-First Architecture                         
ECHO =========================================================================
ECHO.

:: 1. Navigate to Project Directory
cd /d "%~dp0"

:: 2. Pre-startup Database Snapshot Backup
if exist "school.db" (
    if not exist "backups" mkdir "backups"
    set "BACKUP_NAME=backups\snapshot_auto_%date:~10,4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.db"
    set "BACKUP_NAME=%BACKUP_NAME: =0%"
    copy /y "school.db" "%BACKUP_NAME%" >nul 2>&1
    ECHO  [*] Database snapshot secured: %BACKUP_NAME%
)

:: 3. Detect Python Environment (.venv vs System)
set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    ECHO  [*] Virtual environment active: .venv
) else (
    ECHO  [*] Using system Python environment
)

:: 4. Start FastAPI / Uvicorn Server in Background
ECHO  [*] Starting EduManage360 Host Engine on port 8000 ...
start "EduManage360 Server Engine" /min %PYTHON_EXE% -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

:: 5. Wait for Server Initialization
ECHO  [*] Initializing institutional services ...
timeout /t 2 /nobreak >nul

:: 6. Launch Dedicated Desktop App Kiosk Mode
ECHO  [*] Launching EduManage360 Desktop App ...
set "TARGET_URL=http://127.0.0.1:8000/auth.html"

:: Check for Microsoft Edge App Mode
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app="%TARGET_URL%" --window-size=1280,820
    goto :STARTED
)
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app="%TARGET_URL%" --window-size=1280,820
    goto :STARTED
)

:: Check for Google Chrome App Mode
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app="%TARGET_URL%" --window-size=1280,820
    goto :STARTED
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --app="%TARGET_URL%" --window-size=1280,820
    goto :STARTED
)

:: Fallback Default Browser
start "" "%TARGET_URL%"

:STARTED
ECHO.
ECHO =========================================================================
ECHO  [OK] EduManage360 is RUNNING!
ECHO  [OK] Local Portal:   http://127.0.0.1:8000
ECHO  [OK] Offline Wi-Fi:  Accessible from teachers' devices via School LAN
ECHO =========================================================================
ECHO  Keep this console open while using the system.
ECHO  To shut down gracefully, run 'Stop_EduManage360.bat'.
ECHO =========================================================================
ECHO.
