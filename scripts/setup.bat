@echo off
title SaulGPT Setup
color 0a

echo ═══════════════════════════════════════════
echo   SaulGPT - One-Time Setup
echo ═══════════════════════════════════════════
echo.

echo [1/2] Creating Python virtual environment...
if not exist ".venv" (
    python -m venv .venv
)

echo [2/2] Installing dependencies...
echo.

echo   Installing Python packages...
call .venv\Scripts\pip.exe install -r "backend\requirements.txt"

echo.
echo   Installing Node packages...
cd saulgpt-ui
call npm install
cd ..

echo.
echo ═══════════════════════════════════════════
echo   Setup complete!
echo ═══════════════════════════════════════════
echo.
echo   Run 'scripts\start.bat' to launch SaulGPT
echo.
pause