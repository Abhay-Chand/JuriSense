@echo off
title SaulGPT
cd /d "%~dp0.."
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
rem GROQ_API_KEY is loaded from .env file in the project root by python-dotenv

echo ==================================================
echo   SaulGPT - Starting All Services
echo ==================================================
echo.

set "VENV_PYTHON=%~dp0..\.venv\Scripts\python.exe"
set "BACKEND_DIR=%~dp0..\backend"

echo [1/2] Starting Backend API...
start "SaulGPT-Backend" cmd /k ""%VENV_PYTHON%" "%BACKEND_DIR%\api_server.py""

timeout /t 4 /nobreak >nul

echo [2/2] Starting Frontend...
start "SaulGPT-Frontend" cmd /k "cd /d "%~dp0..\saulgpt-ui" && npm run dev"

timeout /t 3 /nobreak >nul

echo Opening browser...
start http://localhost:5173

echo.
echo ==================================================
echo   SaulGPT is running!
echo ==================================================
echo.
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo.
echo   Close the terminal windows to stop the app.
echo   Press any key to close this window...
echo ==================================================
pause >nul