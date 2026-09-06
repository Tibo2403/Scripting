#!/usr/bin/env bash
set -Eeuo pipefail
: "${DEEPINFRA_API_KEY:?DEEPINFRA_API_KEY is required}"
: "${QWEN_MODEL_ID:?QWEN_MODEL_ID is required}"
: "${DEEPSEEK_MODEL_ID:?DEEPSEEK_MODEL_ID is required}"
catalog="$(curl --fail --silent --show-error --connect-timeout 10 --max-time 30 \
  -H "Authorization: Bearer ${DEEPINFRA_API_KEY}" https://api.deepinfra.com/v1/openai/models)"
if ! jq -e '.data | type == "array" and all(.[]; (.id | type == "string"))' >/dev/null <<<"${catalog}"; then
  echo 'DeepInfra returned an invalid model catalogue.' >&2
  exit 1
fi
for model in "${QWEN_MODEL_ID}" "${DEEPSEEK_MODEL_ID}"; do
  if ! jq -e --arg id "${model}" 'any(.data[]; .id == $id)' >/dev/null <<<"${catalog}"; then
    echo 'Requested model is unavailable; select IDs from the DeepInfra models endpoint.' >&2
    exit 1
  fi
done
echo 'DeepInfra model validation passed.'
