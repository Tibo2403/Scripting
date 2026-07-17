#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="deploy-inkling-akash.yaml"
PROFILE="cpu"
MAX_PRICE_UACT="25"
CPU_UNITS="0.5"
MEMORY_SIZE="1Gi"
STORAGE_SIZE="1Gi"
LITELLM_IMAGE="ghcr.io/berriai/litellm:v1.92.0"
DEPLOY=false
DRY_RUN=false

usage() {
  cat <<'EOF'
Generate and optionally submit a cost-optimized Akash SDL for Inkling.

Inkling cannot run locally on one RTX 3090. The optimal low-cost setup is a
small CPU-only LiteLLM gateway forwarding to an OpenAI-compatible Inkling API.
For the absolute lowest cost, call the upstream API directly and skip Akash.

Usage:
  deploy_inkling_akash.sh [options]

Options:
  --profile cpu|rtx3090   Resource profile (default: cpu)
  --cpu UNITS             CPU cores for cpu profile (default: 0.5)
  --memory SIZE           RAM (default: 1Gi)
  --storage SIZE          Ephemeral storage (default: 1Gi)
  --max-price-uact N      Maximum ACT micro-units per block (default: 25)
  --output FILE           Generated SDL path
  --deploy                Submit SDL with provider-services
  --dry-run               Print SDL and estimated maximum monthly cost
  -h, --help              Show help

Required environment variables:
  INKLING_API_BASE        OpenAI-compatible upstream base URL
  INKLING_API_KEY         Upstream API token
  LITELLM_MASTER_KEY      Client-facing gateway key

Optional environment variables:
  INKLING_MODEL_NAME      Upstream model identifier (default: inkling)

Example:
  export INKLING_API_BASE='https://provider.example/v1'
  export INKLING_API_KEY='...'
  export LITELLM_MASTER_KEY="$(openssl rand -hex 32)"
  bash scripts/bash/deploy_inkling_akash.sh --dry-run
  bash scripts/bash/deploy_inkling_akash.sh --deploy
EOF
}

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require_positive_integer() {
  [[ "$2" =~ ^[1-9][0-9]*$ ]] || fail "$1 must be a positive integer"
}

require_cpu_value() {
  [[ "$1" =~ ^([0-9]+([.][0-9]+)?|[0-9]+m)$ ]] || fail "--cpu must be numeric or millicores (for example 0.5 or 500m)"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) [[ $# -ge 2 ]] || fail "--profile requires a value"; PROFILE="$2"; shift 2 ;;
    --cpu) [[ $# -ge 2 ]] || fail "--cpu requires a value"; CPU_UNITS="$2"; shift 2 ;;
    --memory) [[ $# -ge 2 ]] || fail "--memory requires a value"; MEMORY_SIZE="$2"; shift 2 ;;
    --storage) [[ $# -ge 2 ]] || fail "--storage requires a value"; STORAGE_SIZE="$2"; shift 2 ;;
    --max-price-uact) [[ $# -ge 2 ]] || fail "--max-price-uact requires a value"; MAX_PRICE_UACT="$2"; shift 2 ;;
    --output) [[ $# -ge 2 ]] || fail "--output requires a value"; OUTPUT_FILE="$2"; shift 2 ;;
    --deploy) DEPLOY=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

case "$PROFILE" in
  cpu) ;;
  rtx3090)
    printf 'WARNING: RTX 3090 is unused in API gateway mode and can cost hundreds of dollars per month.\n' >&2
    ;;
  *) fail "--profile must be cpu or rtx3090" ;;
esac

require_cpu_value "$CPU_UNITS"
require_positive_integer "--max-price-uact" "$MAX_PRICE_UACT"
[[ "$MEMORY_SIZE" =~ ^[1-9][0-9]*(Mi|Gi)$ ]] || fail "--memory must use Mi or Gi"
[[ "$STORAGE_SIZE" =~ ^[1-9][0-9]*(Mi|Gi)$ ]] || fail "--storage must use Mi or Gi"

: "${INKLING_API_BASE:?Set INKLING_API_BASE}"
: "${INKLING_API_KEY:?Set INKLING_API_KEY}"
: "${LITELLM_MASTER_KEY:?Set LITELLM_MASTER_KEY to a long random secret}"

MODEL_NAME="${INKLING_MODEL_NAME:-inkling}"

GPU_BLOCK=""
if [[ "$PROFILE" == "rtx3090" ]]; then
  GPU_BLOCK=$(cat <<'EOF'
        gpu:
          units: 1
          attributes:
            vendor:
              nvidia:
                - model: rtx3090
                  ram: 24Gi
                  interface: pcie
EOF
)
fi

read -r -d '' SDL <<EOF || true
---
version: "2.0"

services:
  inkling-gateway:
    image: ${LITELLM_IMAGE}
    env:
      - LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY}
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
          units: ${CPU_UNITS}
        memory:
          size: ${MEMORY_SIZE}
        storage:
          size: ${STORAGE_SIZE}
${GPU_BLOCK}
  placement:
    akash:
      pricing:
        inkling-gateway:
          denom: uact
          amount: ${MAX_PRICE_UACT}

deployment:
  inkling-gateway:
    akash:
      profile: inkling-gateway
      count: 1
EOF

# Approximately 432,000 six-second blocks in 30 days; 1,000,000 uACT = 1 ACT.
MONTHLY_MAX_ACT=$(awk -v amount="$MAX_PRICE_UACT" 'BEGIN { printf "%.2f", amount * 432000 / 1000000 }')
printf 'Profile: %s | maximum configured bid: about %s ACT/month (actual winning bid may be lower).\n' "$PROFILE" "$MONTHLY_MAX_ACT" >&2

if [[ "$DRY_RUN" == true ]]; then
  printf '%s\n' "$SDL"
  printf '\nDry run only; nothing was written or deployed.\n' >&2
  exit 0
fi

umask 077
printf '%s\n' "$SDL" >"$OUTPUT_FILE"
printf 'Generated %s\n' "$OUTPUT_FILE"
printf 'Security: this SDL contains secrets. Do not commit it; remove it after deployment.\n' >&2

if [[ "$DEPLOY" == true ]]; then
  command -v provider-services >/dev/null 2>&1 || fail "provider-services CLI is required for --deploy"
  provider-services tx deployment create "$OUTPUT_FILE" --from "${AKASH_KEY_NAME:?Set AKASH_KEY_NAME}" --yes
else
  printf 'Review the SDL, then deploy it with provider-services.\n'
fi
