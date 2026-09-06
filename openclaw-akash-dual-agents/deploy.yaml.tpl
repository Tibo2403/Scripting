version: "2.0"
services:
  openclaw:
    image: {{IMAGE}}
    env:
{{ENV}}
    expose:
      - port: 18789
        as: 18789
        to:
          - global: false
    params:
      storage:
        data:
          mount: /data
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
            size: 8Gi
            attributes:
              persistent: true
              class: beta3
  placement:
    akash:
      pricing:
        openclaw:
          denom: uact
          amount: 25
deployment:
  openclaw:
    akash:
      profile: openclaw
      count: 1
