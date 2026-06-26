#!/usr/bin/env bash
set -Eeuo pipefail

# Install a local Open WebUI + Ollama stack in Docker.
# Defaults are intentionally conservative and configurable through environment
# variables or CLI flags.

CONTAINER_NAME="${CONTAINER_NAME:-ia-souveraine}"
HOST_PORT="${HOST_PORT:-3000}"
WEBUI_VOLUME="${WEBUI_VOLUME:-open-webui}"
OLLAMA_VOLUME="${OLLAMA_VOLUME:-ollama}"
IMAGE="${IMAGE:-ghcr.io/open-webui/open-webui:ollama}"
GPU_MODE="${GPU_MODE:-auto}"
MODEL="${MODEL:-}"
DRY_RUN=0
SKIP_MODEL=0

usage() {
  cat <<'EOF'
Usage: install_ia_souveraine.sh [options]

Options:
  --container-name NAME  Docker container name (default: ia-souveraine)
  --host-port PORT      Host port mapped to Open WebUI (default: 3000)
  --image IMAGE         Docker image (default: ghcr.io/open-webui/open-webui:ollama)
  --gpu MODE            GPU mode: auto, on, off (default: auto)
  --model NAME          Pull one Ollama model after startup
  --skip-model          Do not pull a model
  --dry-run             Print planned Docker commands without running them
  -h, --help            Show this help

Examples:
  bash scripts/bash/install_ia_souveraine.sh --dry-run --skip-model
  bash scripts/bash/install_ia_souveraine.sh --gpu off --model mistral:7b
EOF
}

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run]'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --container-name)
        CONTAINER_NAME="${2:?missing value for --container-name}"
        shift 2
        ;;
      --host-port)
        HOST_PORT="${2:?missing value for --host-port}"
        shift 2
        ;;
      --image)
        IMAGE="${2:?missing value for --image}"
        shift 2
        ;;
      --gpu)
        GPU_MODE="${2:?missing value for --gpu}"
        shift 2
        ;;
      --model)
        MODEL="${2:?missing value for --model}"
        shift 2
        ;;
      --skip-model)
        SKIP_MODEL=1
        shift
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "unknown option: $1"
        ;;
    esac
  done
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    fail "missing command: $command_name"
  fi
}

docker_supports_gpu() {
  command -v nvidia-smi >/dev/null 2>&1 && docker info 2>/dev/null | grep -qi 'nvidia'
}

build_gpu_args() {
  case "$GPU_MODE" in
    on)
      printf '%s\n' "--gpus all"
      ;;
    off)
      printf '%s\n' ""
      ;;
    auto)
      if docker_supports_gpu; then
        printf '%s\n' "--gpus all"
      else
        printf '%s\n' ""
      fi
      ;;
    *)
      fail "GPU mode must be one of: auto, on, off"
      ;;
  esac
}

container_exists() {
  docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"
}

container_running() {
  docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"
}

start_container() {
  log "Starting Open WebUI + Ollama container: $CONTAINER_NAME"

  if [[ "$DRY_RUN" -eq 0 ]] && container_running; then
    log "Container is already running."
    return
  fi

  if [[ "$DRY_RUN" -eq 0 ]] && container_exists; then
    log "Container exists. Starting it."
    run_cmd docker start "$CONTAINER_NAME"
    return
  fi

  local gpu_args
  gpu_args="$(build_gpu_args)"
  if [[ -z "$gpu_args" ]]; then
    log "GPU disabled or unavailable; using CPU mode."
  fi

  # shellcheck disable=SC2086
  run_cmd docker run -d \
    -p "${HOST_PORT}:8080" \
    ${gpu_args} \
    --name "$CONTAINER_NAME" \
    -v "${OLLAMA_VOLUME}:/root/.ollama" \
    -v "${WEBUI_VOLUME}:/app/backend/data" \
    --restart always \
    "$IMAGE"
}

wait_for_ollama() {
  [[ "$DRY_RUN" -eq 1 ]] && return
  log "Waiting for Ollama inside the container..."

  for _ in {1..30}; do
    if docker exec "$CONTAINER_NAME" ollama list >/dev/null 2>&1; then
      log "Ollama is ready."
      return
    fi
    sleep 2
  done

  docker logs --tail 80 "$CONTAINER_NAME" >&2 || true
  fail "Ollama did not become ready in time"
}

pull_model_if_requested() {
  if [[ "$SKIP_MODEL" -eq 1 || -z "$MODEL" ]]; then
    log "No model pull requested."
    return
  fi
  run_cmd docker exec "$CONTAINER_NAME" ollama pull "$MODEL"
}

main() {
  parse_args "$@"
  require_command docker

  if [[ "$DRY_RUN" -eq 0 ]] && ! docker info >/dev/null 2>&1; then
    fail "Docker is unavailable or the daemon is not running"
  fi

  start_container
  wait_for_ollama
  pull_model_if_requested

  log "Open WebUI URL: http://localhost:${HOST_PORT}"
  log "The first created account will be the administrator."
}

main "$@"
