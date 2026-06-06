@echo off
chcp 65001 >nul
title Установка @kukhon.market Agent

echo.
echo ==========================================
echo   Установка зависимостей агента
echo ==========================================
echo.

:: Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    echo Скачай и установи Python с https://python.org
    echo Обязательно поставь галочку "Add Python to PATH"
    pause
    exit /b 1
)

echo [OK] Python найден
python --version

echo.
echo Устанавливаю пакеты...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не удалось установить пакеты.
    echo Попробуй запустить install.bat от имени Администратора.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Установка завершена успешно!
echo ==========================================
echo.
echo Следующий шаг: отредактируй файл .env
echo Затем запусти start.bat
echo.
pause
