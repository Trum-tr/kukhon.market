@echo off
title InstAgent
cd /d C:\InstAgent

echo Stopping old processes...
python -c "import psutil,os;[p.terminate() for p in psutil.process_iter(['pid','cmdline']) if any(x in ' '.join(p.info['cmdline'] or []) for x in ['orchestrator.py','dm_agent.py']) and p.pid!=os.getpid()]" 2>nul
timeout /t 3 /nobreak >nul

echo Starting Orchestrator in background...
set PYTHONUNBUFFERED=1
start /B pythonw -u orchestrator.py

timeout /t 5 /nobreak >nul

echo Checking...
python -c "import psutil;o=any('orchestrator.py' in ' '.join(p.info.get('cmdline') or []) for p in psutil.process_iter(['cmdline']));print('[OK] Orchestrator running' if o else '[!!] Orchestrator NOT running - check orchestrator.log')"

echo.
echo Logs: C:\InstAgent\orchestrator.log
echo To stop: taskkill /F /IM pythonw.exe
pause
