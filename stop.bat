@echo off
REM Stops anything the launcher left running (only this app's processes).
cd /d "%~dp0"
node scripts\stop.mjs
