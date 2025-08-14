@echo off
setlocal enableextensions enabledelayedexpansion
REM ====================================
REM EasyMesh WebRTC Setup and Run Script (Windows)
REM - Installs deps (Python venv + pip, Yarn)
REM - Starts backend (FastAPI on 0.0.0.0:8001)
REM - Starts frontend (React on LAN IP:3000) with proper WebSocket host
REM ====================================

REM Move to repo root (folder of this script)
cd /d "%~dp0"

echo.
echo ========================================
echo   EasyMesh WebRTC Local Setup
echo ========================================
echo.

REM ---------- Check Python ----------
where py >nul 2>&1
if %errorlevel% neq 0 (
    where python >nul 2>&1
)
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org and try again.
    pause
    exit /b 1
)

REM ---------- Check Node.js ----------
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js 18+ from https://nodejs.org and try again.
    pause
    exit /b 1
)

REM ---------- Ensure Yarn ----------
echo.
echo ========================================
echo   Preparing Yarn
echo ========================================
echo.
where yarn >nul 2>&1
if %errorlevel% neq 0 (
    echo Yarn not found in PATH. Installing Yarn classic globally via npm...
    call npm install -g yarn@1.22.22
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install Yarn globally via npm.
        pause
        exit /b 1
    )
)
for /f "delims=" %%V in ('yarn --version 2^>nul') do set YARN_VER=%%V
if not defined YARN_VER (
    echo ERROR: Yarn command is not responding.
    pause
    exit /b 1
)
echo Using Yarn version: %YARN_VER%
set YARN_DISABLE_SELF_UPDATE_CHECK=1

REM ---------- Backend: Python venv + deps ----------
echo.
echo ========================================
echo   Installing Backend Dependencies
echo ========================================
echo.
cd /d "%~dp0backend"
if not exist .venv (
    where py >nul 2>&1 && (py -3 -m venv .venv) || (python -m venv .venv)
)
call .venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt || (echo Backend deps failed & pause & exit /b 1)

REM ---------- Frontend: Yarn deps ----------
echo.
echo ========================================
echo   Installing Frontend Dependencies
echo ========================================
echo.
cd /d "%~dp0frontend"
call yarn --version || (echo Yarn missing & pause & exit /b 1)
call yarn install --network-timeout 600000 || (echo Yarn install failed & pause & exit /b 1)

echo.
echo ========================================
echo   Setting up Environment Variables
echo ========================================
echo.
REM Detect LAN IPv4 via ipconfig, trim, strip (Preferred)
set LAN_IP=
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /C:"IPv4 Address"') do (
  set LAN_IP=%%A
  goto after_ip
)
:after_ip
if not defined LAN_IP set LAN_IP=127.0.0.1
for /f "tokens=* delims= " %%A in ("%LAN_IP%") do set LAN_IP=%%A
set LAN_IP=%LAN_IP:(Preferred)=%
if defined IP_OVERRIDE set LAN_IP=%IP_OVERRIDE%
echo Using LAN IP: %LAN_IP%

REM Ensure CRA picks the correct backend during dev
> ".env.development.local" echo REACT_APP_BACKEND_URL=http://%LAN_IP%:8001

REM ---------- Start Applications ----------
echo.
echo ========================================
echo   Starting Applications
echo ========================================
echo.
cd /d "%~dp0backend"
echo Starting Backend Server (FastAPI) on http://0.0.0.0:8001 ...
start "EasyMesh Backend" cmd /k "call .venv\Scripts\activate && python -m uvicorn server:app --host 0.0.0.0 --port 8001"

timeout /t 2 /nobreak >nul

cd /d "%~dp0frontend"
echo Starting Frontend (React) on http://%LAN_IP%:3000 ...
REM Clear any inherited vars to avoid CRA schema error, then set to LAN
start "EasyMesh Frontend" cmd /k "set \"HOST=\" && set \"WDS_SOCKET_HOST=\" && set \"PORT=\" && set \"HOST=%LAN_IP%\" && set \"WDS_SOCKET_HOST=%LAN_IP%\" && set \"PORT=3000\" && yarn start"

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Backend API: http://%LAN_IP%:8001
echo Frontend App: http://%LAN_IP%:3000
echo.
echo If the app is not reachable on mobile, allow Windows Firewall for ports 3000/8001.
echo.

pause
exit /b 0