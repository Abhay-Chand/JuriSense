@echo off
title SaulGPT
color 0a
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
rem GROQ_API_KEY is loaded from .env file in the project root by python-dotenv

echo ===============================================
echo        SAULGPT - LEGAL INTELLIGENCE
echo ===============================================
echo.
echo  [1] Start SaulGPT
echo  [2] Setup (first time only)
echo  [3] Exit
echo.
choice /c 123 /n /m "Select option (1-3): "

if errorlevel 3 goto :eof
if errorlevel 2 goto setup
if errorlevel 1 goto start

:start
echo Starting Backend...
set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
set "BACKEND_DIR=%~dp0backend"
start "SaulGPT-Backend" cmd /k ""%VENV_PYTHON%" "%BACKEND_DIR%\api_server.py""
timeout /t 4 /nobreak >nul
echo Starting Frontend...
start "SaulGPT-Frontend" cmd /k "cd /d %~dp0saulgpt-ui && npm run dev"
timeout /t 3 /nobreak >nul
start http://localhost:5173
echo.
echo Done! Open http://localhost:5173 in your browser
echo Close the terminal windows to stop.
pause
goto :eof

:setup
echo Installing dependencies...
"%~dp0.venv\Scripts\pip.exe" install -r "%~dp0backend\requirements.txt"
cd /d %~dp0saulgpt-ui
call npm install
cd /d %~dp0
echo Setup complete!
pause
goto :eof