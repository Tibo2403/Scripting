#!/usr/bin/env bash
set -Eeuo pipefail

catalog="$(curl -fsS -H "Authorization: Bearer ${DEEPINFRA_API_KEY}" https://api.deepinfra.com/v1/openai/models)"
for model in "${QWEN_MODEL_ID}" "${DEEPSEEK_MODEL_ID}"; do
  if ! jq -e --arg id "${model}" '.data[]? | select(.id == $id)' >/dev/null <<<"${catalog}"; then
    echo "DeepInfra model unavailable: ${model}" >&2
    echo "Set QWEN_MODEL_ID and DEEPSEEK_MODEL_ID to IDs returned by https://api.deepinfra.com/v1/openai/models" >&2
    exit 1
  fi
done

echo "DeepInfra model validation passed."
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Warning: OPENAI_API_KEY is absent; OpenAI fallbacks will not work. ChatGPT Plus does not supply API credits." >&2
fi
