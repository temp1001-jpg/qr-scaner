# EasyMesh WebRTC - Local Setup Guide

## Quick Start (Windows)

We've created batch files to make local setup and running as easy as possible!

### 🚀 First Time Setup

**Double-click: `setup-and-run.bat`**

This will:
- ✅ Check for Python and Node.js
- ✅ Install Yarn if needed
- ✅ Install all backend dependencies (Python packages)
- ✅ Install all frontend dependencies (Node.js packages)
- ✅ Create environment files
- ✅ Start both servers automatically

### 🏃‍♂️ Quick Run (After Setup)

**Double-click: `run-app.bat`**

This will:
- ✅ Start the backend server (FastAPI on port 8001)
- ✅ Start the frontend server (React on port 3000)
- ✅ Open the app in your browser automatically

### ⏹️ Stop Servers

**Double-click: `stop-app.bat`**

This will safely stop all EasyMesh servers.

---

## Prerequisites

Before running the batch files, make sure you have:

### Required
- **Python 3.8+** - [Download from python.org](https://python.org)
- **Node.js 16+** - [Download from nodejs.org](https://nodejs.org)

### Optional (for data persistence)
- **MongoDB Community Edition** - [Download here](https://www.mongodb.com/try/download/community)

---

## Manual Setup (Alternative)

If you prefer manual setup or are not on Windows:

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend Setup
```bash
cd frontend
yarn install
yarn start
```

---

## Access URLs

- **Frontend (Main App)**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs

---

## Features Included

✨ **Modern Glassmorphism UI** with smooth animations
🎯 **Animated QR Code** with "snake chasing tail" border effect
📱 **WebRTC File Transfer** - Direct peer-to-peer transfers
💬 **Real-time Chat** - Instant messaging between devices
📊 **Progress Tracking** - Visual progress bars for file transfers
🌙 **Dark/Light Mode** - Theme toggle support

---

## Troubleshooting

### Common Issues

**Port Already in Use:**
- Run `stop-app.bat` to kill existing processes
- Or manually close any running Python/Node.js processes

**Dependencies Not Installing:**
- Make sure Python and Node.js are in your system PATH
- Try running Command Prompt as Administrator

**MongoDB Connection Error:**
- The app works without MongoDB (no data persistence)
- Install MongoDB Community Edition for full functionality

**Firewall Issues:**
- Allow Python and Node.js through Windows Firewall
- The app needs to access ports 3000 and 8001

### Getting Help

If you encounter issues:
1. Check that all prerequisites are installed
2. Run `setup-and-run.bat` as Administrator
3. Check the console output in the opened windows for error details

---

## File Structure

```
easymesh/
├── setup-and-run.bat    # First-time setup and run
├── run-app.bat          # Quick start (after setup)
├── stop-app.bat         # Stop all servers
├── backend/             # FastAPI backend
│   ├── server.py
│   ├── requirements.txt
│   └── .env
├── frontend/            # React frontend
│   ├── src/
│   ├── package.json
│   └── .env
└── LOCAL-SETUP.md       # This file
```

---

Happy file transferring! 🚀