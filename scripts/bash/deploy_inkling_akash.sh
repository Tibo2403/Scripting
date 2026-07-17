#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
OUTPUT_FILE="deploy-inkling-akash.yaml"
GPU_MODEL="rtx3090"
GPU_UNITS=1
MODE="api"
MAX_PRICE_UAKT="1000"
DEPLOY=false
DRY_RUN=false

usage() {
  cat <<'EOF'
Generate and optionally submit an Akash SDL for Inkling.

Important:
  Inkling cannot be self-hosted on one RTX 3090 (24 GiB VRAM). The official
  quantized checkpoint needs roughly 600 GB aggregate VRAM. Therefore the
  default mode deploys a LiteLLM gateway that forwards requests to a remote,
  OpenAI-compatible Inkling endpoint.

Usage:
  deploy_inkling_akash.sh [options]

Options:
  --mode api|self-host    Deployment mode (default: api)
  --gpu MODEL             Akash GPU model (default: rtx3090)
  --gpu-units N           Number of GPUs (default: 1)
  --output FILE           Generated SDL path
  --max-price-uakt N      Maximum bid price in uAKT (default: 1000)
  --deploy                Submit the generated SDL with provider-services
  --dry-run               Print actions without writing or deploying
  -h, --help              Show this help

Required environment variables for API mode:
  INKLING_API_BASE        OpenAI-compatible upstream base URL
  INKLING_API_KEY         Upstream API token

Optional environment variables:
  LITELLM_MASTER_KEY      Client-facing gateway key (default: generated warning)
  INKLING_MODEL_NAME      Upstream model identifier (default: inkling)

Examples:
  export INKLING_API_BASE='https://your-provider.example/v1'
  export INKLING_API_KEY='...'
  export LITELLM_MASTER_KEY='change-me'
  bash scripts/bash/deploy_inkling_akash.sh --dry-run
  bash scripts/bash/deploy_inkling_akash.sh --deploy
EOF
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_positive_integer() {
  local name="$1"
  local value="$2"
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || fail "$name must be a positive integer"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ $# -ge 2 ]] || fail "--mode requires a value"
      MODE="$2"
      shift 2
      ;;
    --gpu)
      [[ $# -ge 2 ]] || fail "--gpu requires a value"
      GPU_MODEL="$2"
      shift 2
      ;;
    --gpu-units)
      [[ $# -ge 2 ]] || fail "--gpu-units requires a value"
      GPU_UNITS="$2"
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || fail "--output requires a value"
      OUTPUT_FILE="$2"
      shift 2
      ;;
    --max-price-uakt)
      [[ $# -ge 2 ]] || fail "--max-price-uakt requires a value"
      MAX_PRICE_UAKT="$2"
      shift 2
      ;;
    --deploy)
      DEPLOY=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown option: $1"
      ;;
  esac
done

require_positive_integer "--gpu-units" "$GPU_UNITS"
require_positive_integer "--max-price-uakt" "$MAX_PRICE_UAKT"

case "$MODE" in
  api)
    : "${INKLING_API_BASE:?Set INKLING_API_BASE to the OpenAI-compatible Inkling endpoint}"
    : "${INKLING_API_KEY:?Set INKLING_API_KEY to the upstream API token}"
    ;;
  self-host)
    if [[ "$GPU_MODEL" == "rtx3090" && "$GPU_UNITS" -eq 1 ]]; then
      fail "Inkling self-hosting is impossible on 1x RTX 3090 (24 GiB). Use --mode api, or a supported multi-GPU configuration with at least about 600 GB aggregate VRAM."
    fi
    fail "Self-host mode is intentionally blocked until a supported Inkling inference image and sufficient Blackwell/Hopper hardware are configured."
    ;;
  *)
    fail "--mode must be api or self-host"
    ;;
esac

MODEL_NAME="${INKLING_MODEL_NAME:-inkling}"
MASTER_KEY="${LITELLM_MASTER_KEY:-}"
if [[ -z "$MASTER_KEY" ]]; then
  printf 'WARNING: LITELLM_MASTER_KEY is not set; using a placeholder that must be changed.\n' >&2
  MASTER_KEY="CHANGE_ME_BEFORE_DEPLOYMENT"
fi

read -r -d '' SDL <<EOF || true
---
version: "2.0"

services:
  inkling-gateway:
    image: ghcr.io/berriai/litellm:main-latest
    env:
      - LITELLM_MASTER_KEY=${MASTER_KEY}
      - INKLING_API_BASE=${INKLING_API_BASE}
      - INKLING_API_KEY=${INKLING_API_KEY}
      - INKLING_MODEL_NAME=${MODEL_NAME}
    command:
      - /bin/sh
      - -lc
      - |
        cat >/tmp/litellm.yaml <<'YAML'
        model_list:
          - model_name: inkling
            litellm_params:
              model: openai/\${INKLING_MODEL_NAME}
              api_base: \${INKLING_API_BASE}
              api_key: \${INKLING_API_KEY}
        general_settings:
          master_key: \${LITELLM_MASTER_KEY}
        YAML
        exec litellm --config /tmp/litellm.yaml --host 0.0.0.0 --port 4000
    expose:
      - port: 4000
        as: 80
        to:
          - global: true

profiles:
  compute:
    inkling-gateway:
      resources:
        cpu:
          units: 2
        memory:
          size: 4Gi
        storage:
          size: 8Gi
        gpu:
          units: ${GPU_UNITS}
          attributes:
            vendor:
              nvidia:
                - model: ${GPU_MODEL}
                  ram: 24Gi
                  interface: pcie
  placement:
    akash:
      pricing:
        inkling-gateway:
          denom: uakt
          amount: ${MAX_PRICE_UAKT}

deployment:
  inkling-gateway:
    akash:
      profile: inkling-gateway
      count: 1
EOF

if [[ "$DRY_RUN" == true ]]; then
  printf '%s\n' "$SDL"
  printf '\nDry run only; no file was written and no deployment was submitted.\n' >&2
  exit 0
fi

umask 077
printf '%s\n' "$SDL" >"$OUTPUT_FILE"
printf 'Generated %s\n' "$OUTPUT_FILE"
printf 'Security note: the SDL currently contains secrets. Keep it local, deploy it, then delete it securely.\n' >&2

if [[ "$DEPLOY" == true ]]; then
  command -v provider-services >/dev/null 2>&1 || fail "provider-services CLI is required for --deploy"
  provider-services tx deployment create "$OUTPUT_FILE" --from "${AKASH_KEY_NAME:?Set AKASH_KEY_NAME}" --yes
else
  printf 'Review the SDL, then run:\n  provider-services tx deployment create %q --from "$AKASH_KEY_NAME" --yes\n' "$OUTPUT_FILE"
fi
