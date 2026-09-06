ARG OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:2026.5.26@sha256:ae7ff536446f1bbb57ea51b9b21097d8f299d30d683dcd72644973bc0522f3b3
FROM ${OPENCLAW_IMAGE}
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl jq gh ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/openclaw/config.mjs scripts/openclaw/settings.mjs /opt/openclaw-runtime/
COPY openclaw-akash-dual-agents/agents /opt/openclaw-template/agents
COPY openclaw-akash-dual-agents/scripts /opt/openclaw-template/scripts
RUN chmod +x /opt/openclaw-template/scripts/*.sh \
 && mkdir -p /data/openclaw /data/workspaces /data/repos \
 && chown -R node:node /data /opt/openclaw-template
USER node
ENV OPENCLAW_CONFIG_PATH=/data/openclaw/openclaw.json \
    OPENCLAW_STATE_DIR=/data/openclaw \
    HOME=/home/node
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD node -e "fetch('http://127.0.0.1:'+(process.env.OPENCLAW_PORT||18789)+'/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
ENTRYPOINT ["tini", "-s", "--", "/opt/openclaw-template/scripts/entrypoint.sh"]
