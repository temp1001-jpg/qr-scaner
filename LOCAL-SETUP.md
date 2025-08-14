# Build a single .exe that serves the app locally (Windows 10/11)

This produces one console .exe that starts the FastAPI server, serves the React build, and opens your browser to the correct LAN URL. No Python/Node required for end users.

Prereqs on your build machine only (not end users):
- Python 3.10+ with pip
- Node + Corepack (Yarn)
- Windows 10/11

Quick start (one-click build)
- Double-click build-windows-easymesh.bat from the repo root.
- It will:
  - Enable Corepack + Yarn
  - yarn install + yarn build for the frontend
  - Create a Python venv and install backend deps
  - Download the app icon and bundle everything into dist/easymesh.exe

Manual steps (if you prefer)
1) Build the frontend
- Open PowerShell in the repo root
- yarn --cwd frontend install
- yarn --cwd frontend build
  This creates frontend/build

2) Verify backend can serve the build (dev test)
- pip install -r backend/requirements.txt
- python -m uvicorn backend.server:app --host 0.0.0.0 --port 8001
- Open http://127.0.0.1:8001 to verify the UI loads from FastAPI

3) Create a one-file executable with PyInstaller
- pip install pyinstaller
- From repo root, run:
  pyinstaller --onefile \
    --name easymesh \
    --icon backend/app.ico \
    --add-data "frontend/build;frontend_build" \
    backend/run_local.py

Notes:
- On Windows PowerShell, use a semicolon between source and dest in --add-data.
- The binary will be at dist/easymesh.exe.
- Distribute just that .exe. When launched, a console window appears, the server starts on port 8001, and the default browser opens to your LAN URL.

LAN/offline behavior
- The server binds to 0.0.0.0:8001 so phones on the same Wi‑Fi can reach it.
- The QR code is fetched from the internet; without internet, the plain URL is shown to copy manually.