@echo off
title JuriSense - Indian Legal Intelligence
color 0a

echo ═══════════════════════════════════════════
echo   JuriSense - Starting All Services
echo ═══════════════════════════════════════════
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo [1/3] Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Check backend dependencies
if not exist "backend\__pycache__" (
    echo [2/3] Installing backend dependencies...
    cd backend
    pip install -r requirements.txt 2>nul
    cd ..
)

REM Check frontend dependencies
if not exist "jurisense-ui\node_modules" (
    echo [3/3] Installing frontend dependencies...
    cd jurisense-ui
    npm install
    cd ..
)

echo.
echo Starting services...
echo.

REM Start backend in background
start "JuriSense - Backend" cmd /k "cd backend && python api_server.py"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend
start "JuriSense - Frontend" cmd /k "cd jurisense-ui && npm run dev"

echo ═══════════════════════════════════════════
echo   JuriSense is running!
echo.
echo   Backend API:  http://localhost:8000
echo   Frontend:    http://localhost:5173
echo.
echo   Press any key to exit this window...
echo ═══════════════════════════════════════════
pause >nul