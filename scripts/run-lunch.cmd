@echo off
cd /d "%~dp0.."
if not exist logs mkdir logs
echo ===== %DATE% %TIME% =====>> logs\lunch.log
py -3 -m lunchbot >> logs\lunch.log 2>&1
if errorlevel 1 python -m lunchbot >> logs\lunch.log 2>&1
