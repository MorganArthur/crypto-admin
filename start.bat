@echo off
chcp 65001 >nul
title Crypto Admin - One Click Start

echo ========================================
echo    Crypto Admin Full Stack Application
echo ========================================
echo.

REM Check if running in correct directory
if not exist "backend\api_server.py" (
    echo Error: Please run this script from project root directory
    pause
    exit /b 1
)

if not exist "frontend\package.json" (
    echo Error: Please run this script from project root directory
    pause
    exit /b 1
)

echo [1/3] Checking environment...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not detected, please install Python first
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Node.js not detected, please install Node.js first
    pause
    exit /b 1
)

echo [2/3] Starting backend service (FastAPI)...
start "Crypto Admin - Backend" cmd /k "cd backend && ..\venv\Scripts\activate && python api_server.py"

echo Waiting for backend service to start...
timeout /t 5 /nobreak >nul

echo [3/3] Starting frontend service (Vite + React)...
start "Crypto Admin - Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo    Services started successfully!
echo ========================================
echo.
echo Backend API docs: http://localhost:8000/docs
echo Frontend UI:      http://localhost:5173 (or check actual address in frontend window)
echo.
echo Tips:
echo - Two command windows opened for backend and frontend services
echo - Close windows to stop corresponding services
echo - Press any key to exit this startup script (won't affect running services)
echo ========================================
pause >nul