@echo off
setlocal enableextensions enabledelayedexpansion
REM ====================================
REM EasyMesh WebRTC Setup and Run Script (Windows)
REM - Installs deps (Python venv + pip, Yarn)
REM - Starts backend (FastAPI on 0.0.0.0:8001)
REM - Starts frontend (React on LAN IP:3000 so mobiles can access)
REM - No labels/subroutine calls to avoid parser issues
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

REM ---------- Ensure Yarn (prefer global yarn classic) ----------
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
        echo If you are behind a proxy, configure npm proxy first:
        echo   npm config set proxy http://user:pass@host:port
        echo   npm config set https-proxy http://user:pass@host:port
        pause
        exit /b 1
    )
)

for /f "delims=" %%V in ('yarn --version 2^>nul') do set YARN_VER=%%V
if not defined YARN_VER (
    echo ERROR: Yarn command is not responding.
    echo Try: npm install -g yarn@1.22.22
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
    echo Creating virtual environment in backend\.venv ...
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create Python virtual environment
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

python -m pip install --upgrade pip setuptools wheel
if %errorlevel% neq 0 (
    echo ERROR: Failed to upgrade pip/setuptools/wheel
    pause
    exit /b 1
)

pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python dependencies
    pause
    exit /b 1
)

REM ---------- Frontend: Yarn deps ----------
echo.
echo ========================================
echo   Installing Frontend Dependencies
echo ========================================
echo.

cd /d "%~dp0frontend"

echo Checking Yarn availability...
call yarn --version
if %errorlevel% neq 0 (
    echo ERROR: Yarn not available after install.
    pause
    exit /b 1
)

echo Installing Node.js packages with Yarn (this can take a while)...
call yarn install --network-timeout 600000
if %errorlevel% neq 0 (
    echo ERROR: yarn install failed. If you are behind a proxy, configure Yarn:
    echo   yarn config set proxy http://user:pass@host:port
    echo   yarn config set https-proxy http://user:pass@host:port
    echo Full manual command:
    echo   cd frontend && yarn cache clean && yarn install --network-timeout 600000 --verbose
    pause
    exit /b 1
)
echo Yarn install complete.

REM ---------- Environment Setup ----------
echo.
echo ========================================
echo   Setting up Environment Variables
echo ========================================
echo.

REM Detect LAN IPv4 address using PowerShell (fallback to 127.0.0.1)
for /f "usebackq tokens=*" %%I in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.InterfaceOperationalStatus -eq 'Up' -and $_.IPAddress -notmatch '^127\.' } ^| Select-Object -ExpandProperty IPAddress -First 1)"`) do set LAN_IP=%%I
if not defined LAN_IP set LAN_IP=127.0.0.1

REM Optional override: set IP_OVERRIDE=192.168.100.1 before running this script
if defined IP_OVERRIDE set LAN_IP=%IP_OVERRIDE%

echo Using LAN IP: %LAN_IP%

REM Ensure frontend .env exists with HOST/PORT defaults (not strictly required)
if not exist ".env" (
    > ".env" echo HOST=0.0.0.0
    >> ".env" echo PORT=3000
)

REM Create development override so frontend uses local backend via LAN
> ".env.development.local" echo REACT_APP_BACKEND_URL=http://%LAN_IP%:8001

REM ---------- Start Applications ----------
echo.
echo ========================================
echo   Starting Applications
echo ========================================
echo.

cd /d "%~dp0backend"
echo Starting Backend Server (FastAPI) on http://localhost:8001 ...
start "EasyMesh Backend" cmd /k "call .venv\Scripts\activate && python -m uvicorn server:app --host 0.0.0.0 --port 8001"

timeout /t 3 /nobreak >nul

cd /d "%~dp0frontend"
echo Starting Frontend (React) on http://%LAN_IP%:3000 ...
start "EasyMesh Frontend" cmd /k "set HOST=%LAN_IP% && set WDS_SOCKET_HOST=%LAN_IP% && set PORT=3000 && yarn start"

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Backend API: http://%LAN_IP%:8001
console
echo Frontend App: http://%LAN_IP%:3000
echo.
echo Two new command windows have opened:
echo   1. Backend (FastAPI) - Port 8001
echo   2. Frontend (React) - Port 3000
echo.
echo If the React app does not open automatically, navigate to:
echo   http://%LAN_IP%:3000
echo.
echo To stop the servers, close both command windows or press Ctrl+C in them.
echo.

pause
exit /b 0