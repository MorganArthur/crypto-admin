@echo off
chcp 65001 >nul
title Crypto Admin - Stop Services

echo ========================================
echo    Crypto Admin - Stop All Services
echo ========================================
echo.

echo Stopping backend and frontend services...
echo.

REM Stop windows with "Crypto Admin" title
taskkill /FI "WINDOWTITLE eq Crypto Admin - Backend*" /F >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Backend service stopped
) else (
    echo [INFO] Backend service not running or failed to stop
)

taskkill /FI "WINDOWTITLE eq Crypto Admin - Frontend*" /F >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Frontend service stopped
) else (
    echo [INFO] Frontend service not running or failed to stop
)

echo.
echo ========================================
echo    Services stopped
echo ========================================
echo.
pause