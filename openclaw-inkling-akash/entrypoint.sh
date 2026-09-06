#!/bin/sh
set -eu
umask 077
OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-/home/node/.openclaw}"
OPENCLAW_CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-${OPENCLAW_STATE_DIR}/openclaw.json}"
export OPENCLAW_STATE_DIR OPENCLAW_CONFIG_PATH
node "${OPENCLAW_RUNTIME_DIR:-/opt/openclaw-runtime}/config.mjs" inkling "${OPENCLAW_CONFIG_PATH}"
openclaw config validate
exec openclaw gateway --port "${OPENCLAW_PORT:-18789}"
