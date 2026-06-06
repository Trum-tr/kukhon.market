@echo off
chcp 65001 >nul
title Остановка агентов

cd /d "%~dp0"
echo Останавливаю агентов...

python -c "
import psutil, os
stopped = 0
for p in psutil.process_iter(['pid','cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        if ('orchestrator.py' in cmd or 'dm_agent.py' in cmd) and p.pid != os.getpid():
            p.terminate()
            stopped += 1
            print(f'  Остановлен: {cmd[-40:]}')
    except: pass
print(f'Остановлено процессов: {stopped}')
"

echo.
echo Все агенты остановлены.
pause
