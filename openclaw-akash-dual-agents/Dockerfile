ARG OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:latest
FROM ${OPENCLAW_IMAGE}

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl jq ca-certificates \
 && curl -fsSL https://github.com/cli/cli/releases/latest/download/gh_2.76.2_linux_amd64.tar.gz | tar -xz -C /tmp \
 && install /tmp/gh_2.76.2_linux_amd64/bin/gh /usr/local/bin/gh \
 && rm -rf /var/lib/apt/lists/* /tmp/gh_*

COPY openclaw/openclaw.json /opt/openclaw-template/openclaw.json
COPY agents /opt/openclaw-template/agents
COPY scripts /opt/openclaw-template/scripts
RUN chmod +x /opt/openclaw-template/scripts/*.sh \
 && mkdir -p /data/openclaw /data/workspaces /data/repos \
 && chown -R node:node /data /opt/openclaw-template

USER node
ENV OPENCLAW_CONFIG_PATH=/data/openclaw/openclaw.json \
    OPENCLAW_STATE_DIR=/data/openclaw \
    HOME=/home/node
ENTRYPOINT ["/opt/openclaw-template/scripts/entrypoint.sh"]
