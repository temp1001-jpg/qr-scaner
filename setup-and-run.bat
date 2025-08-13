@echo off
REM ====================================
REM EasyMesh WebRTC Setup and Run Script
REM ====================================

echo.
echo ========================================
echo   EasyMesh WebRTC Local Setup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js 16+ from https://nodejs.org
    pause
    exit /b 1
)

REM Check if Yarn is installed
yarn --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Yarn not found. Installing Yarn globally...
    npm install -g yarn
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install Yarn
        pause
        exit /b 1
    )
)

echo ========================================
echo   Installing Backend Dependencies
echo ========================================
echo.

REM Navigate to backend directory and install Python dependencies
cd /d "%~dp0backend"
echo Installing Python packages from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Installing Frontend Dependencies
echo ========================================
echo.

REM Navigate to frontend directory and install Node.js dependencies
cd /d "%~dp0frontend"
echo Installing Node.js packages with Yarn...
yarn install
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Node.js dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Setting up Environment Variables
echo ========================================
echo.

REM Create backend .env file if it doesn't exist
cd /d "%~dp0backend"
if not exist ".env" (
    echo Creating backend .env file...
    echo MONGO_URL=mongodb://localhost:27017/easymesh> .env
    echo Environment file created: backend/.env
) else (
    echo Backend .env file already exists
)

REM Create frontend .env file if it doesn't exist
cd /d "%~dp0frontend"
if not exist ".env" (
    echo Creating frontend .env file...
    echo REACT_APP_BACKEND_URL=http://localhost:8001> .env
    echo Environment file created: frontend/.env
) else (
    echo Frontend .env file already exists
)

echo.
echo ========================================
echo   Checking MongoDB Connection
echo ========================================
echo.

REM Check if MongoDB is running (optional - will work without it)
python -c "from pymongo import MongoClient; MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=2000).server_info()" 2>nul
if %errorlevel% neq 0 (
    echo WARNING: MongoDB is not running on localhost:27017
    echo You can install MongoDB Community Edition from: https://www.mongodb.com/try/download/community
    echo The app will still work but without data persistence.
    echo.
)

echo.
echo ========================================
echo   Starting Applications
echo ========================================
echo.

REM Start backend server in a new window
cd /d "%~dp0backend"
echo Starting Backend Server (FastAPI)...
start "EasyMesh Backend" cmd /c "python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend server in a new window
cd /d "%~dp0frontend"  
echo Starting Frontend Server (React)...
start "EasyMesh Frontend" cmd /c "yarn start"

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Backend Server: http://localhost:8001
echo Frontend App:   http://localhost:3000
echo.
echo Two new command windows have opened:
echo   1. Backend (FastAPI) - Port 8001
echo   2. Frontend (React) - Port 3000
echo.
echo The React app should open automatically in your browser.
echo If not, manually navigate to: http://localhost:3000
echo.
echo To stop the servers, close both command windows or press Ctrl+C
echo.

pause