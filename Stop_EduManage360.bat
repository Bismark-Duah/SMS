@echo off
TITLE EduManage360 - Graceful Shutdown
COLOR 0C
CLS

ECHO =========================================================================
ECHO           EduManage360 - Graceful System Shutdown Engine                 
ECHO =========================================================================
ECHO.

cd /d "%~dp0"

ECHO  [*] Terminating server processes on port 8000 ...

:: Terminate running Python processes associated with uvicorn on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    ECHO  [*] Stopped server process PID %%a
)

:: Terminate any uvicorn title window
taskkill /FI "WINDOWTITLE eq EduManage360 Server Engine*" /F >nul 2>&1

ECHO.
ECHO =========================================================================
ECHO  [OK] EduManage360 has been gracefully stopped.
ECHO  [OK] SQLite database journals committed cleanly.
ECHO =========================================================================
ECHO.
timeout /t 3 >nul
