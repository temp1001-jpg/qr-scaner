@echo off
REM ====================================
REM EasyMesh WebRTC Quick Run Script
REM (Assumes dependencies are installed)
REM ====================================

echo.
echo ========================================
echo   EasyMesh WebRTC Quick Start
echo ========================================
echo.

REM Start backend server
cd /d "%~dp0backend"
echo Starting Backend Server...
start "EasyMesh Backend" cmd /c "python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload"

REM Wait for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend server
cd /d "%~dp0frontend"
echo Starting Frontend Server...
start "EasyMesh Frontend" cmd /c "yarn start"

echo.
echo ========================================
echo   Servers Started!
echo ========================================
echo.
echo Backend: http://localhost:8001
echo Frontend: http://localhost:3000
echo.
echo Opening in browser...
timeout /t 5 /nobreak >nul
start http://localhost:3000

echo.
echo Both servers are running in separate windows.
echo Close this window or press any key to continue...
pause >nul