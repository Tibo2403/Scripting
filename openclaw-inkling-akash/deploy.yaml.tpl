---
version: "2.0"

services:
  openclaw:
    image: ${OPENCLAW_IMAGE}
    env:
      - INKLING_API_KEY=${INKLING_API_KEY}
      - INKLING_BASE_URL=${INKLING_BASE_URL}
      - INKLING_MODEL=${INKLING_MODEL}
      - OPENCLAW_GATEWAY_TOKEN=${OPENCLAW_GATEWAY_TOKEN}
      - OPENCLAW_PORT=18789
      - OPENCLAW_STATE_DIR=/home/node/.openclaw
    expose:
      - port: 18789
        as: 18789
        to:
          - global: true
    params:
      storage:
        data:
          mount: /home/node/.openclaw
          readOnly: false

profiles:
  compute:
    openclaw:
      resources:
        cpu:
          units: 1
        memory:
          size: 2Gi
        storage:
          - size: 1Gi
          - name: data
            size: 5Gi
            attributes:
              persistent: true
              class: beta3
  placement:
    dcloud:
      pricing:
        openclaw:
          denom: uakt
          amount: 10000

deployment:
  openclaw:
    dcloud:
      profile: openclaw
      count: 1
