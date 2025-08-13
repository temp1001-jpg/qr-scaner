#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." &>/dev/null && pwd)"
cd "$REPO_ROOT"

stop_by_pidfile() {
  local name="$1"
  local pidfile=".pids/${name}.pid"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" >/dev/null 2>&1; then
      echo "Stopping $name (PID $pid)"
      kill "$pid" || true
      sleep 1
      if kill -0 "$pid" >/dev/null 2>&1; then
        echo "Force killing $name (PID $pid)"
        kill -9 "$pid" || true
      fi
    else
      echo "$name not running (stale PID file)"
    fi
    rm -f "$pidfile"
  else
    echo "No PID file for $name"
  fi
}

stop_by_pidfile backend
stop_by_pidfile frontend

echo "All services stopped."