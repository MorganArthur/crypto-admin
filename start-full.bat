@echo off
chcp 65001 >nul
title Crypto Admin - Full Startup (with Environment Check)

echo ========================================
echo    Crypto Admin Full Startup Script
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

echo [Step 1/6] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not detected, please install Python 3.8+
    pause
    exit /b 1
)
echo [OK] Python installed

echo.
echo [Step 2/6] Checking Node.js environment...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Node.js not detected, please install Node.js
    pause
    exit /b 1
)
echo [OK] Node.js installed

echo.
echo [Step 3/6] Checking backend dependencies...
if not exist "venv\Scripts\activate.bat" (
    echo Creating Python virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

echo Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
pip install -q -r backend\requirements.txt
if %errorlevel% neq 0 (
    echo Warning: Errors occurred while installing backend dependencies, will try to start anyway
) else (
    echo [OK] Backend dependencies installed
)

echo.
echo [Step 4/6] Checking frontend dependencies...
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies (this may take a few minutes)...
    cd frontend
    call npm install
    if %errorlevel% neq 0 (
        echo Error: Failed to install frontend dependencies
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo [OK] Frontend dependencies installed
) else (
    echo [OK] Frontend dependencies already exist
)

echo.
echo [Step 5/6] Checking .env configuration file...
if not exist "backend\.env" (
    echo Creating default .env file...
    copy "backend\.env.example" "backend\.env" >nul
    echo [OK] Created backend\.env file
    echo Tip: To use DeepSeek API, edit backend\.env file and add your API Key
) else (
    echo [OK] .env file already exists
)

echo.
echo [Step 6/6] Starting services...
echo.

REM Start backend
echo Starting backend service (FastAPI on port 8000)...
start "Crypto Admin - Backend" cmd /k "cd backend && ..\venv\Scripts\activate && python api_server.py"

echo Waiting for backend service to start...
timeout /t 5 /nobreak >nul

REM Start frontend
echo Starting frontend service (Vite + React)...
start "Crypto Admin - Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo    [OK] All services started!
echo ========================================
echo.
echo Access URLs:
echo   - Backend API docs: http://localhost:8000/docs
echo   - Frontend UI:      http://localhost:5173 (or check actual address in frontend window)
echo.
echo Tips:
echo   - Two separate command windows opened for backend and frontend
echo   - Close windows to stop corresponding services
echo   - Use stop.bat to quickly stop all services
echo   - First startup may take longer to install dependencies
echo.
echo ========================================
pause >nul