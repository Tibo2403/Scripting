ARG OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:2026.7.1
FROM ${OPENCLAW_IMAGE}

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/crewai-admin
COPY requirements.txt ./requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY crewai_admin_mcp.py webhook_proxy.py container-entrypoint.sh ./
RUN chmod 0555 container-entrypoint.sh crewai_admin_mcp.py webhook_proxy.py \
    && mkdir -p /var/lib/openclaw-crewai-admin \
    && chown -R node:node /var/lib/openclaw-crewai-admin

USER node
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"

ENTRYPOINT ["/opt/crewai-admin/container-entrypoint.sh"]

