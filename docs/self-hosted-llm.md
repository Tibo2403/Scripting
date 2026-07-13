# Self-Hosted LLM Stack

`scripts/bash/install_ia_souveraine.sh` installs a local Open WebUI + Ollama
stack with Docker. It is intended for personal or lab use where prompts, chats,
and model files should stay on infrastructure you control.

## What It Starts

- Open WebUI, exposed on `http://localhost:3000` by default.
- Ollama inside the same container image.
- Persistent Docker volumes for WebUI data and Ollama model storage.
- Optional GPU acceleration when Docker reports NVIDIA GPU support.

The first account created in Open WebUI becomes the administrator.

## Dry Run

Review the planned Docker command before creating anything:

```bash
bash scripts/bash/install_ia_souveraine.sh --dry-run --skip-model
```

## Install

Start the stack without pulling a model:

```bash
bash scripts/bash/install_ia_souveraine.sh --skip-model
```

Start the stack and pull a model:

```bash
bash scripts/bash/install_ia_souveraine.sh --model mistral:7b
```

Use CPU mode explicitly:

```bash
bash scripts/bash/install_ia_souveraine.sh --gpu off --model mistral:7b
```

Use another host port:

```bash
bash scripts/bash/install_ia_souveraine.sh --host-port 8080 --skip-model
```

## Configuration

The installer accepts CLI flags and environment variables:

| Setting | Default | Description |
| --- | --- | --- |
| `CONTAINER_NAME` | `ia-souveraine` | Docker container name. |
| `HOST_PORT` | `3000` | Host port mapped to Open WebUI. |
| `WEBUI_VOLUME` | `open-webui` | Persistent WebUI data volume. |
| `OLLAMA_VOLUME` | `ollama` | Persistent Ollama model volume. |
| `IMAGE` | `ghcr.io/open-webui/open-webui:ollama` | Container image. |
| `GPU_MODE` | `auto` | GPU behavior: `auto`, `on`, or `off`. |

CLI flags take precedence for the matching setting.

## Persistence

The installer stores data in Docker volumes:

- `open-webui` for Open WebUI configuration, users, and chats.
- `ollama` for downloaded Ollama models.

Removing the container does not remove these volumes unless you delete them
manually with Docker commands.

## Troubleshooting

Check whether Docker is available:

```bash
docker info
```

Check the container logs:

```bash
docker logs ia-souveraine
```

Open a shell inside the container:

```bash
docker exec -it ia-souveraine bash
```

List available Ollama models:

```bash
docker exec ia-souveraine ollama list
```

## Cloud LiteLLM Microservice

`scripts/bash/install_llm_microservice.sh` is the API-focused counterpart to
the Open WebUI installer. It uses the same Ollama + LiteLLM architecture on
three deployment targets:

- `vm`: install and start the stack on a Debian or Ubuntu VM.
- `compose`: generate a portable bundle for any Docker-compatible cloud.
- `akash`: generate an Akash SDL ready for Akash Console.

In every mode, the stack contains two services:

- Ollama, reachable only inside the Compose network.
- LiteLLM Proxy, exposing an authenticated OpenAI-compatible `/v1` API.

If `--master-key` and `LITELLM_MASTER_KEY` are omitted, the script generates a
random key and stores it only in protected deployment files. For production,
override the default container images with versioned tags or digests.

Review the default VM deployment without changing anything:

```bash
bash scripts/bash/install_llm_microservice.sh --dry-run
```

### Linux VM

Install a CPU deployment accessible only from the VM itself:

```bash
sudo bash scripts/bash/install_llm_microservice.sh \
  --platform vm \
  --gpu off \
  --model qwen2.5:7b
```

To serve remote clients, bind the gateway to the VM interfaces. Restrict port
4000 to trusted client IPs in the cloud security group or host firewall, and
terminate TLS in a reverse proxy:

```bash
sudo bash scripts/bash/install_llm_microservice.sh \
  --platform vm \
  --host 0.0.0.0 \
  --model mistral:7b \
  --gpu auto \
  --with-openclaw \
  --openclaw-base-url https://llm.example.com
```

Call it with an OpenAI SDK by using `http://VM_IP:4000/v1` as the base URL,
the configured master key as the API key, and `local-llm` as the model. The
public model name can be changed with `--model-alias`.

The generated stack is stored in `/opt/llm-microservice`. Its `.env` file is
mode `0600`, while Ollama model data lives in a named Docker volume. Re-running
the installer updates the Compose and LiteLLM configuration without deleting
the downloaded models.

### Portable Docker Cloud

Generate the same stack without installing or starting anything locally:

```bash
bash scripts/bash/install_llm_microservice.sh \
  --platform compose \
  --output-dir ./llm-microservice-deploy \
  --host 0.0.0.0 \
  --with-openclaw \
  --openclaw-base-url https://llm.example.com
```

Copy that directory to any Docker host on AWS, Azure, GCP, OVHcloud, Hetzner,
Scaleway, or another provider, then run:

```bash
cd llm-microservice-deploy
docker compose -p llm-microservice up -d
docker compose -p llm-microservice exec ollama ollama pull qwen2.5:7b
```

Portable Compose generation maps `--gpu auto` to CPU because it cannot inspect
the destination host. Pass `--gpu on` when the destination has the NVIDIA
Container Toolkit.

The output directory is ignored by this repository because its `.env` file
contains the API key.

### Akash Network

Generate an SDL for a CPU lease:

```bash
bash scripts/bash/install_llm_microservice.sh --akash
```

For a GPU lease, request an NVIDIA model supported by Akash providers:

```bash
bash scripts/bash/install_llm_microservice.sh \
  --akash \
  --gpu on \
  --akash-gpu-model rtx4090 \
  --akash-memory 24Gi \
  --akash-storage 80Gi \
  --with-openclaw
```

The result is `llm-microservice-deploy/deploy.yaml`. In Akash Console, create
a deployment with **Build your template**, upload this file, review provider
bids, and create the lease. Ollama downloads the selected model at startup and
keeps it on a provider-local persistent volume. LiteLLM receives an internal
DNS endpoint named `ollama` and is the only globally exposed service.

Akash notes:

- `--gpu auto` becomes CPU mode because SDL resources must be declared before
  provider bids; use `--gpu on` to reserve a GPU.
- Persistent storage remains attached across workload restarts on the selected
  provider, but is lost when the lease is closed or moved to another provider.
- The generated SDL contains the LiteLLM key and is written with mode `0600`.
  Never commit or share it.
- Provider availability and price depend on the requested GPU, memory, storage,
  and the `--akash-max-price` ceiling.

### OpenClaw Agents as LiteLLM Clients

OpenClaw sits in front of the microservice as the agent runtime and API client.
LiteLLM does not call OpenClaw: an OpenClaw agent sends an OpenAI-compatible
request to LiteLLM, LiteLLM routes it to Ollama, then the response returns along
the same path:

```text
User or channel
    -> OpenClaw agent
        -> LiteLLM /v1 gateway
            -> Ollama model on a VM, Docker cloud, or Akash
```

Before selecting that model alias, the companion
[`compute_cost_arbitrage.py`](compute-cost-arbitrage.md) utility can compare the
owned GPU's electricity and amortization against rented compute and hosted API
prices while enforcing a minimum quality score. It is advisory: OpenClaw still
calls LiteLLM, and an operator or approved automation applies the recommended
alias after health, privacy, and quality checks.

This separation keeps agent tools, sessions, channels, and permissions in
OpenClaw while model authentication, aliases, routing, quotas, and observability
belong to the LiteLLM gateway. Several OpenClaw agents can share the same
gateway and use different model aliases or LiteLLM keys.

Add `--with-openclaw` to any deployment mode. The installer generates two
additional client artifacts next to the deployment files:

- `openclaw-litellm.json5`: a standalone OpenClaw configuration with a
  `litellm` provider and a strict `sovereign` agent.
- `openclaw.env`: the matching `LITELLM_API_KEY`, written with mode `0600`.

The generated agent uses `litellm/local-llm` by default. It declares
`fallbacks: []`, so a failed sovereign model request is not silently sent to a
different model. Change the agent id, advertised model limits, or public
gateway URL when generating the files:

```bash
bash scripts/bash/install_llm_microservice.sh \
  --platform compose \
  --with-openclaw \
  --openclaw-agent-id research \
  --openclaw-context-window 32768 \
  --openclaw-max-tokens 8192 \
  --openclaw-base-url https://llm.example.com
```

For a VM installation, the files are placed in `/opt/llm-microservice`. For
portable Compose and Akash generation, they are placed in the selected output
directory. Load the key and point OpenClaw at the generated configuration:

```bash
set -a
. ./openclaw.env
set +a
OPENCLAW_CONFIG_PATH="$PWD/openclaw-litellm.json5" openclaw config validate
OPENCLAW_CONFIG_PATH="$PWD/openclaw-litellm.json5" openclaw models status \
  --agent sovereign
```

The generated JSON5 is a bootstrap configuration. If OpenClaw already has a
configuration, do not replace it wholesale: merge the
`models.providers.litellm` block and assign the desired entries in
`agents.list` to `litellm/local-llm`. Keep `fallbacks: []` on agents that must
remain sovereign; other agents can have explicitly approved fallback models.

Akash does not provide the final public URI until a lease is created. After
deployment, replace `https://akash-litellm.example` in
`openclaw-litellm.json5` with the HTTPS URI shown for the LiteLLM service. The
provider `baseUrl` is the gateway origin, without `/v1`.

Operational recommendations:

- Run OpenClaw on a trusted control host and expose only LiteLLM through TLS.
- Restrict the LiteLLM endpoint by firewall, VPN, or an authenticated ingress;
  never expose Ollama directly.
- The bootstrap uses the LiteLLM master key. For production, configure
  LiteLLM persistence and issue a separate virtual key per agent or agent
  group, then replace the value in `openclaw.env`.
- Never commit `openclaw.env`, `.env`, or an Akash SDL containing a key.
- Match `--openclaw-context-window` and `--openclaw-max-tokens` to the selected
  Ollama model, especially for models used by tool-calling agents.
- If OpenClaw reaches a LiteLLM private LAN address rather than loopback, review
  OpenClaw's private-network request policy before enabling that access.
