# Build a single .exe that serves the app locally (Windows 10/11)

This produces one console .exe that starts the FastAPI server, serves the React build, and opens your browser to the correct LAN URL. No Python/Node required for end users.

Prereqs on your build machine only (not end users):
- Python 3.10+ with pip
- Node + Corepack (Yarn)
- Windows 10/11

Steps
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
    --add-data "frontend/build;frontend_build" \
    backend/run_local.py

Notes:
- On Windows PowerShell, use a semicolon between source and dest in --add-data as shown above.
- The binary will be at dist/easymesh.exe.
- Distribute just that .exe. When launched, a console window appears, the server starts on port 8001, and the default browser opens to your LAN URL.

LAN/offline behavior
- The server binds to 0.0.0.0:8001 so phones on the same Wi‑Fi can reach it.
- The QR code now prefers your LAN IP (not 127.0.0.1) when running locally, so peers can join by scanning it.

Troubleshooting
- If the browser opens at 127.0.0.1, it’s OK for the host PC, but your phone won’t reach that URL. Look in the app’s left panel; the QR link and URL will show the LAN address detected by the server. You can also manually browse to http://<your_lan_ip>:8001.
- If your PC has multiple adapters, the app will pick the first private IPv4 it finds. You can change which one by editing backend/run_local.py to choose a different index.