@echo off
REM Algaroshy Farm launcher (Windows). Everything runs in this one window.
REM   run.bat          dev mode  (hot reload)        -> http://localhost:5173
REM   run.bat demo     demo mode (phones + PWA)      -> http://localhost:4173
REM   run.bat reset    clear alarms/commands/events/telemetry first (add 'demo' to combine)
REM First run sets itself up (Python venv, packages, .env). Ctrl+C stops everything.
cd /d "%~dp0"
where node >nul 2>nul || (echo [!] Node.js 20+ is required: https://nodejs.org & pause & exit /b 1)
node scripts\start.mjs %*
if errorlevel 1 pause
