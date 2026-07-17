ARG OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:latest
FROM ${OPENCLAW_IMAGE}

USER root
COPY entrypoint.sh /usr/local/bin/openclaw-inkling-entrypoint
RUN chmod 0755 /usr/local/bin/openclaw-inkling-entrypoint \
    && mkdir -p /home/node/.openclaw \
    && chown -R node:node /home/node/.openclaw

USER node
ENTRYPOINT ["/usr/local/bin/openclaw-inkling-entrypoint"]
