@echo off
setlocal enableextensions enabledelayedexpansion

REM ==============================================
REM EasyMesh Windows One-Click Builder (single exe)
REM - Builds React frontend
REM - Creates Python venv and installs backend deps
REM - Bundles everything into dist\easymesh.exe (one file)
REM ==============================================

REM Move to repo root (this script should be at the root)
pushd %~dp0

set ICON_URL=https://customer-assets.emergentagent.com/job_no-install-app/artifacts/2lwp5ctt_download.ico
set ICON_PATH=backend\app.ico

REM 1) Ensure Corepack + Yarn are ready
where corepack >nul 2>&1
if %errorlevel% neq 0 (
  echo Corepack not found. Please install Node.js 18+ which includes Corepack.
  echo Download: https://nodejs.org
  pause
  exit /b 1
)

call corepack enable
call corepack prepare yarn@stable --activate

REM 2) Install frontend deps and build
pushd frontend
call yarn install || goto :err
call yarn build || goto :err
popd

REM 3) Prepare Python venv and deps
where py >nul 2>&1
if %errorlevel% equ 0 (
  py -3 -m venv .venv || goto :err
) else (
  where python >nul 2>&1 || (
    echo Python not found. Please install Python 3.10+ from https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
  python -m venv .venv || goto :err
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip || goto :err
pip install -r backend\requirements.txt || goto :err
pip install pyinstaller || goto :err

REM 4) Download app icon
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%ICON_URL%' -OutFile '%ICON_PATH%' -UseBasicParsing } catch { Write-Error $_; exit 1 }" || goto :err

REM 5) Clean previous builds
if exist build rd /s /q build
if exist dist rd /s /q dist
if exist __pycache__ rd /s /q __pycache__
for /d %%D in (backend\__pycache__) do rd /s /q "%%D" 2>nul
for /f %%F in ('dir /b /s *.spec 2^>nul') do del /f /q "%%F" 2>nul

REM 6) Build single-file exe
pyinstaller --noconfirm --clean --onefile --name easymesh --icon "%ICON_PATH%" --add-data "frontend/build;frontend_build" backend\run_local.py || goto :err

REM 7) Done
if exist dist\easymesh.exe (
  echo.
  echo ✅ Build complete: dist\easymesh.exe
  echo Double-click to run. A console will open, server will start on port 8001, and your browser will open.
  echo If Windows Firewall prompts, allow access on Private networks so phones on the same Wi-Fi can connect.
  echo.
) else (
  echo ❌ Build failed: exe not found in dist\
  goto :err
)

popd
exit /b 0

:err
popd
echo.
echo Build failed. See the messages above for details.
exit /b 1