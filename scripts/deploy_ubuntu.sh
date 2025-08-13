#!/usr/bin/env bash
set -euo pipefail

# Ubuntu deployment script for this React (frontend) + FastAPI (backend) app
# - Installs system dependencies (Node.js + Yarn, Python, build tools)
# - Builds the frontend
# - Installs backend requirements into a virtualenv
# - Starts backend (uvicorn on 0.0.0.0:8001) and serves frontend build on port 3000
#
# Usage:
#   sudo bash scripts/deploy_ubuntu.sh
#
# Notes:
# - This script prefers Yarn (not npm)
# - It will only create frontend/.env if it does not exist; it will NOT modify existing .env files
# - Default REACT_APP_BACKEND_URL is http://localhost:8001/api (you can change when prompted)
# - MongoDB is optional; backend connects lazily and only used by sample endpoints

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." &>/dev/null && pwd)"
cd "$REPO_ROOT"

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "Please run with sudo: sudo bash scripts/deploy_ubuntu.sh"
    exit 1
  fi
}

install_apt_packages() {
  echo "[1/6] Installing system packages..."
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    curl git python3 python3-venv python3-pip build-essential lsb-release ca-certificates
}

install_node_and_yarn() {
  echo "[2/6] Installing Node.js 22.x and enabling Yarn (Corepack)..."
  if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
  else
    echo "Node already installed: $(node -v)"
  fi
  # Ensure corepack and pin Yarn to 1.x as declared in package.json
  corepack enable || true
  corepack prepare yarn@1.22.22 --activate || true
  echo "Yarn version: $(yarn -v)"
}

setup_python_venv_and_dependencies() {
  echo "[3/6] Creating Python virtualenv and installing backend requirements..."
  python3 -m venv backend/.venv
  # shellcheck disable=SC1091
  source backend/.venv/bin/activate
  pip install --upgrade pip setuptools wheel
  pip install -r backend/requirements.txt
  deactivate
}

configure_frontend_env() {
  echo "[4/6] Configuring frontend environment..."
  local default_backend_url="http://localhost:8001/api"
  if [[ ! -f frontend/.env ]]; then
    read -r -p "Enter REACT_APP_BACKEND_URL for frontend (default: ${default_backend_url}): " REACT_URL
    REACT_URL="${REACT_URL:-$default_backend_url}"
    if [[ "$REACT_URL" != *"/api"* ]]; then
      echo "Warning: REACT_APP_BACKEND_URL should include '/api' prefix; adding automatically."
      if [[ "$REACT_URL" == */ ]]; then REACT_URL="${REACT_URL}api"; else REACT_URL="${REACT_URL}/api"; fi
    fi
    echo "REACT_APP_BACKEND_URL=$REACT_URL" > frontend/.env
    echo "Created frontend/.env with REACT_APP_BACKEND_URL=$REACT_URL"
  else
    echo "frontend/.env already exists. Keeping existing variables."
  fi
}

build_frontend() {
  echo "[5/6] Installing frontend deps and building..."
  pushd frontend >/dev/null
  yarn install --frozen-lockfile || yarn install
  yarn build
  popd >/dev/null
}

start_services() {
  echo "[6/6] Starting backend and serving frontend..."
  mkdir -p logs .pids

  # Start backend (FastAPI via uvicorn) on 0.0.0.0:8001
  if pgrep -f "uvicorn backend.server:app" >/dev/null 2>&1; then
    echo "Backend already running. Skipping start."
  else
    bash -lc 'cd '"$REPO_ROOT"' && source backend/.venv/bin/activate && nohup python -m uvicorn backend.server:app --host 0.0.0.0 --port 8001 > logs/backend.log 2>&1 & echo $! > .pids/backend.pid'
    echo "Started backend (PID: $(cat .pids/backend.pid))"
  fi

  # Serve frontend/build on port 3000 using serve
  if pgrep -f "serve -s frontend/build" >/dev/null 2>&1; then
    echo "Frontend server already running. Skipping start."
  else
    # Try to use globally installed 'serve' if available; otherwise use yarn dlx
    if command -v serve >/dev/null 2>&1; then
      nohup serve -s frontend/build -l 3000 > logs/frontend.log 2>&1 & echo $! > .pids/frontend.pid
    else
      # Avoid npm; use yarn dlx
      nohup yarn dlx serve -s frontend/build -l 3000 > logs/frontend.log 2>&1 & echo $! > .pids/frontend.pid
    fi
    echo "Started frontend static server (PID: $(cat .pids/frontend.pid))"
  fi

  echo "\nDeployment complete. Access URLs:"
  echo "  Frontend: http://<server-ip-or-domain>:3000"
  echo "  Backend:  http://<server-ip-or-domain>:8001/api"
  echo "Logs:   $REPO_ROOT/logs"
  echo "PIDs:   $REPO_ROOT/.pids"
}

main() {
  require_root
  install_apt_packages
  install_node_and_yarn
  setup_python_venv_and_dependencies
  configure_frontend_env
  build_frontend
  start_services
}

main "$@"