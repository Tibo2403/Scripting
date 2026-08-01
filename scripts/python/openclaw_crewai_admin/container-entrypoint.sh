#!/usr/bin/env bash
set -euo pipefail

gateway_pid=""

shutdown() {
  if [[ -n "$gateway_pid" ]]; then
    kill -TERM "$gateway_pid" 2>/dev/null || true
    wait "$gateway_pid" 2>/dev/null || true
  fi
}
trap shutdown EXIT INT TERM

node /app/dist/index.js gateway --bind loopback --port 18789 &
gateway_pid="$!"

for _attempt in $(seq 1 60); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18789/healthz', timeout=1)" 2>/dev/null; then
    break
  fi
  if ! kill -0 "$gateway_pid" 2>/dev/null; then
    wait "$gateway_pid"
    exit 1
  fi
  sleep 1
done

if ! kill -0 "$gateway_pid" 2>/dev/null; then
  exit 1
fi

python3 /opt/crewai-admin/webhook_proxy.py

