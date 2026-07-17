# Inkling on Akash

## Hardware reality

Inkling has 975 billion total parameters and 41 billion active parameters. Its official BF16 checkpoint requires about 2 TB of aggregate VRAM, while the NVFP4 checkpoint requires about 600 GB and Blackwell-class FP4 support. A single RTX 3090 provides only 24 GiB of VRAM and therefore cannot self-host Inkling.

The helper in `scripts/bash/deploy_inkling_akash.sh` deliberately refuses `--mode self-host` on one RTX 3090. Its default `api` mode deploys a LiteLLM gateway on an Akash RTX 3090 and forwards requests to a remote OpenAI-compatible endpoint that actually hosts Inkling.

> Cost note: the GPU is not used for inference in API mode. Keeping the requested RTX 3090 preserves the original deployment choice, but a CPU-only Akash deployment is cheaper. Remove the `gpu` block from the generated SDL when the upstream API performs all inference.

## Prerequisites

- An Akash account funded for deployments.
- The `provider-services` CLI configured with an Akash key.
- An OpenAI-compatible provider endpoint exposing Inkling.
- The provider API token.

## Generate the SDL safely

```bash
export INKLING_API_BASE='https://provider.example/v1'
export INKLING_API_KEY='replace-me'
export LITELLM_MASTER_KEY='replace-with-a-long-random-secret'

bash scripts/bash/deploy_inkling_akash.sh --dry-run
bash scripts/bash/deploy_inkling_akash.sh --output deploy-inkling-akash.yaml
```

The generated SDL contains secrets. Do not commit it. Restrict its permissions, submit it, and remove it after deployment.

## Submit the deployment

```bash
export AKASH_KEY_NAME='your-akash-key'
bash scripts/bash/deploy_inkling_akash.sh --deploy
```

Alternatively, generate and review the SDL first:

```bash
provider-services tx deployment create deploy-inkling-akash.yaml \
  --from "$AKASH_KEY_NAME" \
  --yes
```

After selecting a provider lease and sending the manifest using your normal Akash workflow, the gateway exposes an OpenAI-compatible endpoint on port 80. Clients use the model name `inkling` and authenticate with `LITELLM_MASTER_KEY`.

## Test the gateway

```bash
curl "http://YOUR_AKASH_HOST/v1/chat/completions" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "inkling",
    "messages": [{"role": "user", "content": "Bonjour"}]
  }'
```

## Self-hosting

Do not use one RTX 3090 for local Inkling inference. Use hardware supported by the selected checkpoint and inference engine. At the initial Inkling release, the practical official configurations require several high-memory Hopper or Blackwell GPUs, not consumer 24 GiB cards.
