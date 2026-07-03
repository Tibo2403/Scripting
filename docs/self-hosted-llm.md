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
