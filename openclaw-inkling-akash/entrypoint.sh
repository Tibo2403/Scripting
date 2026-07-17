#!/bin/sh
set -eu

: "${INKLING_API_KEY:?INKLING_API_KEY est obligatoire}"
: "${OPENCLAW_GATEWAY_TOKEN:?OPENCLAW_GATEWAY_TOKEN est obligatoire}"

INKLING_BASE_URL="${INKLING_BASE_URL:-https://ai-gateway.vercel.sh/v1}"
INKLING_MODEL="${INKLING_MODEL:-thinkingmachines/inkling}"
OPENCLAW_PORT="${OPENCLAW_PORT:-18789}"
OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-/home/node/.openclaw}"
OPENCLAW_CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-${OPENCLAW_STATE_DIR}/openclaw.json}"

export INKLING_API_KEY OPENCLAW_GATEWAY_TOKEN INKLING_BASE_URL INKLING_MODEL
export OPENCLAW_PORT OPENCLAW_STATE_DIR OPENCLAW_CONFIG_PATH

mkdir -p "${OPENCLAW_STATE_DIR}"

node <<'NODE'
const fs = require('fs');
const path = require('path');

const model = process.env.INKLING_MODEL;
const configPath = process.env.OPENCLAW_CONFIG_PATH;
const config = {
  models: {
    mode: 'merge',
    providers: {
      inkling: {
        baseUrl: process.env.INKLING_BASE_URL,
        apiKey: process.env.INKLING_API_KEY,
        api: 'openai-completions',
        models: [{
          id: model,
          name: 'Inkling',
          reasoning: true,
          input: ['text', 'image'],
          contextWindow: 262144,
          maxTokens: 32768
        }]
      }
    }
  },
  agents: {
    defaults: {
      model: { primary: `inkling/${model}` },
      models: { [`inkling/${model}`]: { alias: 'Inkling' } }
    }
  },
  gateway: {
    bind: 'lan',
    port: Number(process.env.OPENCLAW_PORT),
    auth: {
      mode: 'token',
      token: process.env.OPENCLAW_GATEWAY_TOKEN
    }
  }
};

fs.mkdirSync(path.dirname(configPath), { recursive: true });
fs.writeFileSync(configPath, JSON.stringify(config, null, 2), { mode: 0o600 });
NODE

echo "Démarrage OpenClaw sur 0.0.0.0:${OPENCLAW_PORT}"
echo "Modèle: inkling/${INKLING_MODEL}"
exec openclaw gateway --port "${OPENCLAW_PORT}"
