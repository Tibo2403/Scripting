#!/usr/bin/env bash
set -Eeuo pipefail
for profile in dual inkling; do
  docker run --rm --network none --entrypoint sh \
    -e OPENCLAW_GATEWAY_TOKEN=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
    -e DEEPINFRA_API_KEY=fixture -e GITHUB_TOKEN=fixture \
    -e TOKEN_BOT_A=111:aaa -e TOKEN_BOT_B=222:bbb \
    -e QWEN_MODEL_ID=vendor/qwen -e DEEPSEEK_MODEL_ID=vendor/deepseek \
    -e REPOSITORIES=acme/repo -e INKLING_API_KEY=fixture -e INKLING_MODEL=vendor/model \
    -e OPENCLAW_CONFIG_PATH=/tmp/openclaw-test.json \
    "$profile:test" -c 'node /opt/openclaw-runtime/config.mjs "$1" "$OPENCLAW_CONFIG_PATH" && openclaw config validate' sh "$profile"
done
