ARG OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:2026.5.26@sha256:ae7ff536446f1bbb57ea51b9b21097d8f299d30d683dcd72644973bc0522f3b3
FROM ${OPENCLAW_IMAGE}
USER root
COPY scripts/openclaw/config.mjs scripts/openclaw/settings.mjs /opt/openclaw-runtime/
COPY openclaw-inkling-akash/entrypoint.sh /usr/local/bin/openclaw-inkling-entrypoint
RUN chmod 0755 /usr/local/bin/openclaw-inkling-entrypoint \
 && mkdir -p /home/node/.openclaw \
 && chown -R node:node /home/node/.openclaw
USER node
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD node -e "fetch('http://127.0.0.1:'+(process.env.OPENCLAW_PORT||18789)+'/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
ENTRYPOINT ["tini", "-s", "--", "/usr/local/bin/openclaw-inkling-entrypoint"]
