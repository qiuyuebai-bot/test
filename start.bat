@echo off
setlocal
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js 18 or newer is required.
    pause
    exit /b 1
)

node scripts\start.mjs %*
set "APP_EXIT_CODE=%ERRORLEVEL%"

if not "%APP_EXIT_CODE%"=="0" pause
exit /b %APP_EXIT_CODE%
