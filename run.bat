@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title KelasYar - Class Homework Manager

cd /d "%~dp0"

echo ==========================================================
echo    KelasYar - Class Homework Manager  (run.bat)
echo ==========================================================
echo.

REM ---------- locate Python ----------
set "PYTHON=python"
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Python not found!
        echo.
        echo Please install Python 3.10+ from https://www.python.org/downloads/
        echo IMPORTANT: during installation check "Add Python to PATH".
        echo.
        pause
        exit /b 1
    )
    set "PYTHON=py"
)

REM ---------- virtual environment ----------
if not exist .venv (
    echo [1/3] Creating virtual environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

echo [2/3] Installing dependencies (first run may take a few minutes)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies. Check your internet connection.
    pause
    exit /b 1
)

echo [3/3] Starting KelasYar (migrations + API + Telegram bot)...
echo.
echo   - first run: a .env file is created automatically; if this is
echo     your first time, stop the server, open .env and fill in:
echo       TELEGRAM_BOT_TOKEN        (from @BotFather)
echo       SUPER_ADMIN_TELEGRAM_IDS  (your numeric Telegram ID)
echo     then run this file again.
echo.
echo   - PROXY / Hiddify: if Telegram is blocked on your network,
echo     turn Hiddify ON - the bot auto-detects it (port 12334 and
echo     other common local proxy ports). Direct connection is tried
echo     first, so nothing changes when Hiddify is off. You can also
echo     set TELEGRAM_PROXY_URL in .env manually.
echo.
echo   - web panel : http://localhost:8000/admin
echo   - API docs  : http://localhost:8000/docs
echo.
python run.py

echo.
echo Server stopped.
pause
