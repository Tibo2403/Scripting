#!/usr/bin/env bash
set -euo pipefail

gateway_pid=""
proxy_pid=""

shutdown() {
  if [[ -n "$gateway_pid" ]]; then
    kill -TERM "$gateway_pid" 2>/dev/null || true
  fi
  if [[ -n "$proxy_pid" ]]; then
    kill -TERM "$proxy_pid" 2>/dev/null || true
  fi
  [[ -z "$gateway_pid" ]] || wait "$gateway_pid" 2>/dev/null || true
  [[ -z "$proxy_pid" ]] || wait "$proxy_pid" 2>/dev/null || true
}
trap shutdown EXIT INT TERM

node /app/dist/index.js gateway --bind loopback --port 18789 &
gateway_pid="$!"

gateway_ready=false
for _attempt in $(seq 1 60); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18789/healthz', timeout=1)" 2>/dev/null; then
    gateway_ready=true
    break
  fi
  if ! kill -0 "$gateway_pid" 2>/dev/null; then
    wait "$gateway_pid"
    exit 1
  fi
  sleep 1
done

if [[ "$gateway_ready" != true ]]; then
  echo "OpenClaw n'est pas devenu sain dans le délai imparti." >&2
  exit 1
fi

python3 /opt/crewai-admin/webhook_proxy.py &
proxy_pid="$!"

# Le conteneur s'arrête dès que le Gateway ou le proxy s'arrête.
wait -n "$gateway_pid" "$proxy_pid"
exit 1
