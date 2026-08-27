@echo off
TITLE EduManage360 - Restart Engine
COLOR 0E
CLS

ECHO =========================================================================
ECHO           EduManage360 - System Restart Engine                           
ECHO =========================================================================
ECHO.

cd /d "%~dp0"

call "Stop_EduManage360.bat"
timeout /t 1 /nobreak >nul
call "Start_EduManage360.bat"
