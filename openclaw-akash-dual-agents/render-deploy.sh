#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec node "${SCRIPT_DIR}/../scripts/openclaw/render.mjs" dual \
  "${1:-${SCRIPT_DIR}/.env}" "${2:-${SCRIPT_DIR}/deploy.yaml}" "${@:3}"
