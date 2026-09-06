#!/usr/bin/env bash
set -euo pipefail

ALLOW_MISSING_SECRETS=false
if [[ "${1:-}" == "--allow-missing-secrets" ]]; then
  ALLOW_MISSING_SECRETS=true
elif [[ $# -gt 0 ]]; then
  printf 'ERROR: unknown option: %s\n' "$1" >&2
  exit 2
fi

CONFIG_PATH="${LITELLM_CONFIG_PATH:-$PWD/.devcontainer/litellm-inkling.yaml}"
GATEWAY_HOST="${LITELLM_HOST:-0.0.0.0}"
GATEWAY_PORT="${LITELLM_PORT:-4000}"
STATE_DIR="${LITELLM_STATE_DIR:-/tmp/inkling-gateway}"
PID_FILE="$STATE_DIR/litellm.pid"
LOG_FILE="$STATE_DIR/litellm.log"

missing=()
[[ -n "${INKLING_API_KEY:-}" ]] || missing+=(INKLING_API_KEY)
[[ -n "${LITELLM_MASTER_KEY:-}" ]] || missing+=(LITELLM_MASTER_KEY)

if (( ${#missing[@]} > 0 )); then
  printf 'Inkling gateway not started: missing Codespaces secret(s): %s\n' "${missing[*]}" >&2
  if [[ "$ALLOW_MISSING_SECRETS" == true ]]; then
    exit 0
  fi
  exit 1
fi

[[ -f "$CONFIG_PATH" ]] || {
  printf 'ERROR: LiteLLM config not found: %s\n' "$CONFIG_PATH" >&2
  exit 1
}

mkdir -p "$STATE_DIR"
if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE")"
  if [[ "$existing_pid" =~ ^[0-9]+$ ]] && kill -0 "$existing_pid" 2>/dev/null; then
    printf 'Inkling gateway already running (PID %s).\n' "$existing_pid"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

nohup litellm --config "$CONFIG_PATH" --host "$GATEWAY_HOST" --port "$GATEWAY_PORT" >"$LOG_FILE" 2>&1 &
gateway_pid=$!
printf '%s\n' "$gateway_pid" >"$PID_FILE"

for _ in {1..30}; do
  if curl --silent --fail "http://127.0.0.1:${GATEWAY_PORT}/health/liveliness" >/dev/null; then
    printf 'Inkling gateway ready on port %s (PID %s).\n' "$GATEWAY_PORT" "$gateway_pid"
    exit 0
  fi
  if ! kill -0 "$gateway_pid" 2>/dev/null; then
    printf 'ERROR: Inkling gateway stopped during startup. See %s\n' "$LOG_FILE" >&2
    exit 1
  fi
  sleep 1
done

printf 'ERROR: Inkling gateway did not become ready. See %s\n' "$LOG_FILE" >&2
exit 1
