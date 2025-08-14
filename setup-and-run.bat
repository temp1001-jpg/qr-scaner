@echo off
setlocal enableextensions enabledelayedexpansion
REM ====================================
REM EasyMesh WebRTC Setup and Run Script (Windows)
REM - Installs deps (Python venv + pip, Yarn), builds frontend
REM - Starts backend (FastAPI on 0.0.0.0:8001) and frontend (React on 3000)
REM - Keeps windows open so you can see errors instead of auto-closing
REM ====================================

REM Move to repo root (folder of this script)
cd /d "%~dp0"

call :print_header "EasyMesh WebRTC Local Setup"

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

REM ---------- Ensure Yarn (prefer global yarn classic to avoid Corepack issues on Windows) ----------
call :print_section "Preparing Yarn"
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

REM Verify Yarn works and print version
for /f "delims=" %%V in ('yarn --version 2^>nul') do set YARN_VER=%%V
if not defined YARN_VER (
    echo ERROR: Yarn command is not responding. Please try:
    echo   npm install -g yarn@1.22.22
    echo   then re-run this script.
    pause
    exit /b 1
)
echo Using Yarn version: %YARN_VER%

REM Disable Yarn self-update check to avoid network stalls
set YARN_DISABLE_SELF_UPDATE_CHECK=1

REM ---------- Backend: Python venv + deps ----------
call :print_section "Installing Backend Dependencies"
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
call :print_section "Installing Frontend Dependencies"
cd /d "%~dp0frontend"

echo Checking Yarn availability...
call yarn --version
if %errorlevel% neq 0 (
    echo ERROR: Yarn not available after install.
    pause
    exit /b 1
)

echo Installing Node.js packages with Yarn (this can take a while)...
REM Increase network timeout to avoid stalls on slow networks
call yarn install --network-timeout 600000
if %errorlevel% neq 0 (
    echo ERROR: yarn install failed. If you are behind a proxy, configure Yarn:
    echo   yarn config set proxy http://user:pass@host:port
    echo   yarn config set https-proxy http://user:pass@host:port
    echo Full re-run command (manual):
    echo   cd frontend ^&^& yarn cache clean ^&^& yarn install --network-timeout 600000 --verbose
    pause
    exit /b 1
)

REM ---------- Environment Setup ----------
echo.
echo ========================================
echo   Setting up Environment Variables
echo ========================================
echo.
cd /d "%~dp0frontend"
if not exist ".env" (
    echo Creating frontend .env file...
    echo REACT_APP_BACKEND_URL=http://localhost:8001/api> .env
    echo Environment file created: frontend/.env
) else (
    echo Frontend .env file already exists (leaving untouched)
)

REM ---------- Start Applications ----------
call :print_section "Starting Applications"

REM Start backend in new window, keep it open with cmd /k
cd /d "%~dp0backend"
echo Starting Backend Server (FastAPI) on http://localhost:8001 ...
start "EasyMesh Backend" cmd /k "call .venv\Scripts\activate && python -m uvicorn server:app --host 0.0.0.0 --port 8001"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend in new window, keep it open with cmd /k
cd /d "%~dp0frontend"
REM Detect LAN IPv4 address using PowerShell (fallback to 127.0.0.1)
for /f "usebackq tokens=*" %%I in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceOperationalStatus -eq 'Up' -and $_.IPAddress -notmatch '^127\.' } | Select-Object -ExpandProperty IPAddress -First 1)"`) do set LAN_IP=%%I
if not defined LAN_IP set LAN_IP=127.0.0.1

echo Starting Frontend (React) on http://%LAN_IP%:3000 ...
start "EasyMesh Frontend" cmd /k "set HOST=%LAN_IP% && set WDS_SOCKET_HOST=%LAN_IP% && set PORT=3000 && yarn start"

call :print_footer

REM Keep this window open
pause
exit /b 0

:print_header
cls
set MSG=%~1
echo.
echo ========================================
echo   %MSG%
echo ========================================
echo.
exit /b 0

:print_section
set MSG=%~1
echo.
echo ========================================
echo   %MSG%
echo ========================================
echo.
exit /b 0

:print_footer
echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Backend API: http://localhost:8001/api
echo Frontend App: http://localhost:3000
echo.
echo Two new command windows have opened:
echo   1. Backend (FastAPI) - Port 8001
echo   2. Frontend (React) - Port 3000
echo.
echo If the React app does not open automatically, navigate to:
echo   http://localhost:3000
echo.
echo To stop the servers, close both command windows or press Ctrl+C in them.
echo.
exit /b 0