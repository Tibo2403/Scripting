#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-${SCRIPT_DIR}/.env}"
OUTPUT_FILE="${2:-${SCRIPT_DIR}/deploy.yaml}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Fichier absent: ${ENV_FILE}" >&2
  echo "Copie .env.example vers .env puis renseigne les secrets." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

required=(OPENCLAW_IMAGE INKLING_API_KEY INKLING_BASE_URL INKLING_MODEL OPENCLAW_GATEWAY_TOKEN)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Variable obligatoire absente: ${name}" >&2
    exit 1
  fi
done

if ! command -v envsubst >/dev/null 2>&1; then
  echo "envsubst est requis (paquet gettext-base)." >&2
  exit 1
fi

envsubst < "${SCRIPT_DIR}/deploy.yaml.tpl" > "${OUTPUT_FILE}"
chmod 600 "${OUTPUT_FILE}"
echo "SDL généré: ${OUTPUT_FILE}"
