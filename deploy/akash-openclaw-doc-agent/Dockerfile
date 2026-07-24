ARG OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:2026.5.26
FROM ${OPENCLAW_IMAGE}

USER root

COPY --chown=node:node config/openclaw.json /home/node/.openclaw/openclaw.json
COPY --chown=node:node workspace/AGENTS.md /workspace/AGENTS.md
COPY --chown=node:node runtime/run-agent.mjs /app/akash/run-agent.mjs

RUN install -d -m 0700 -o node -g node /home/node/.openclaw \
    && install -d -m 0750 -o node -g node /workspace /app/akash

USER node

ENV HOME=/home/node \
    OPENCLAW_CONFIG_PATH=/home/node/.openclaw/openclaw.json \
    OPENCLAW_DISABLE_BONJOUR=1 \
    ADMIN_ENABLED=false \
    REGISTRATION_ENABLED=false \
    PUBLIC_ACCESS=false \
    ALLOW_SHELL=false \
    ALLOW_DOCKER=false \
    ALLOW_TERMINAL=false

EXPOSE 8080

CMD ["node", "/app/akash/run-agent.mjs"]
