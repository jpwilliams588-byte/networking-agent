@echo off
REM This is what the once-a-day scheduled task runs. It archives untouched
REM leads, then finds & enriches new ones (up to the daily cap), appending a
REM summary line to daily_log.txt.
cd /d "%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" daily_run.py
