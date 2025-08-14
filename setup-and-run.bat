@echo off
setlocal enableextensions enabledelayedexpansion
REM ====================================
REM EasyMesh WebRTC Setup and Run Script (Windows)
REM - Installs deps (Python venv + pip, Yarn via Corepack), builds frontend
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

REM ---------- Ensure Yarn via Corepack (preferred) ----------
where corepack >nul 2>&1
if %errorlevel% equ 0 (
    echo Enabling Corepack and preparing Yarn 1...
    call corepack enable >nul 2>&1
    call corepack prepare yarn@1.22.22 --activate >nul 2>&1
) else (
    echo Corepack not available. Falling back to global Yarn install via npm.
    where yarn >nul 2>&1
    if %errorlevel% neq 0 (
        echo Installing Yarn globally...
        call npm install -g yarn
        if %errorlevel% neq 0 (
            echo ERROR: Failed to install Yarn
            pause
            exit /b 1
        )
    )
)

REM ---------- Backend: Python venv + deps ----------
call :print_section "Installing Backend Dependencies"
cd /d "%~dp0backend"

if not exist .venv (
    echo Creating virtual environment in backend\.venv ...
    rem Prefer py launcher if available
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

REM Optional: install watchfiles to support --reload on Windows if desired
pip install watchfiles >nul 2>&1

REM ---------- Frontend: Yarn deps ----------
call :print_section "Installing Frontend Dependencies"
cd /d "%~dp0frontend"

yarn --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Yarn is not available after setup.
    echo Please ensure Yarn is installed (Corepack or npm -g) and try again.
    pause
    exit /b 1
)

echo Installing Node.js packages with Yarn...
yarn install
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Node.js dependencies
    pause
    exit /b 1
)

REM ---------- Environment Setup ----------
call :print_section "Setting up Environment Variables"

REM Do NOT create backend .env (MongoDB removed)

REM Create frontend .env if it doesn't exist, ensure /api prefix in URL
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
echo Starting Frontend (React) on http://localhost:3000 ...
start "EasyMesh Frontend" cmd /k "yarn start"

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