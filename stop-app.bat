@echo off
REM ====================================
REM EasyMesh WebRTC Stop Script
REM ====================================

echo.
echo ========================================
echo   Stopping EasyMesh WebRTC Servers
echo ========================================
echo.

REM Kill all Python processes running uvicorn
echo Stopping Backend Server (Python/FastAPI)...
taskkill /f /im python.exe >nul 2>&1

REM Kill all Node.js processes
echo Stopping Frontend Server (Node.js/React)...
taskkill /f /im node.exe >nul 2>&1

REM Kill any remaining processes by window title
taskkill /fi "WindowTitle eq EasyMesh Backend*" /f >nul 2>&1
taskkill /fi "WindowTitle eq EasyMesh Frontend*" /f >nul 2>&1

echo.
echo ========================================
echo   All Servers Stopped
echo ========================================
echo.
echo All EasyMesh WebRTC servers have been stopped.
echo.

pause