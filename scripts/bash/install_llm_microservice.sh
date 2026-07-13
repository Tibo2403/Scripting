#!/usr/bin/env bash
set -Eeuo pipefail

# Deploy a persistent Ollama model behind a LiteLLM/OpenAI-compatible API.
# Supported targets: Debian/Ubuntu VM, portable Docker Compose bundle, Akash SDL.

SERVICE_NAME="${SERVICE_NAME:-llm-microservice}"
PLATFORM="${PLATFORM:-vm}"
INSTALL_DIR="${INSTALL_DIR:-/opt/llm-microservice}"
OUTPUT_DIR="${OUTPUT_DIR:-./llm-microservice-deploy}"
MODEL="${MODEL:-qwen2.5:7b}"
MODEL_ALIAS="${MODEL_ALIAS:-local-llm}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-4000}"
GPU_MODE="${GPU_MODE:-auto}"
LITELLM_IMAGE="${LITELLM_IMAGE:-docker.litellm.ai/berriai/litellm:main-latest}"
OLLAMA_IMAGE="${OLLAMA_IMAGE:-ollama/ollama:latest}"
LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:-}"
AKASH_GPU_MODEL="${AKASH_GPU_MODEL:-rtx4090}"
AKASH_CPU="${AKASH_CPU:-4}"
AKASH_MEMORY="${AKASH_MEMORY:-16Gi}"
AKASH_MODEL_STORAGE="${AKASH_MODEL_STORAGE:-50Gi}"
AKASH_MAX_PRICE="${AKASH_MAX_PRICE:-10000}"
WITH_OPENCLAW="${WITH_OPENCLAW:-0}"
OPENCLAW_BASE_URL="${OPENCLAW_BASE_URL:-}"
OPENCLAW_AGENT_ID="${OPENCLAW_AGENT_ID:-sovereign}"
OPENCLAW_CONTEXT_WINDOW="${OPENCLAW_CONTEXT_WINDOW:-32768}"
OPENCLAW_MAX_TOKENS="${OPENCLAW_MAX_TOKENS:-8192}"
DRY_RUN=0
SKIP_DOCKER_INSTALL=0
SKIP_MODEL=0

usage() {
  cat <<'EOF'
Usage: install_llm_microservice.sh [options]

Deploy Ollama behind an authenticated LiteLLM/OpenAI-compatible API.

Targets:
  --platform vm       Install/start on a Debian or Ubuntu VM (default)
  --platform compose  Generate a portable Docker Compose bundle
  --platform akash    Generate an Akash SDL deployment bundle
  --akash             Shortcut for --platform akash

Common options:
  --output-dir PATH   Output for compose/akash (default: ./llm-microservice-deploy)
  --model NAME        Ollama model (default: qwen2.5:7b)
  --model-alias NAME  Public API model name (default: local-llm)
  --master-key KEY    LiteLLM key; generated automatically when omitted
  --gpu MODE          GPU mode: auto, on, off (default: auto)
  --litellm-image IMG LiteLLM container image
  --ollama-image IMG  Ollama container image
  --skip-model        Do not pull the model automatically
  --with-openclaw     Generate an OpenClaw client configuration for LiteLLM
  --openclaw-base-url URL
                      Public LiteLLM origin seen by OpenClaw (without /v1)
  --openclaw-agent-id ID
                      Example OpenClaw agent id (default: sovereign)
  --openclaw-context-window N
                      Model context window advertised to OpenClaw (default: 32768)
  --openclaw-max-tokens N
                      Model output limit advertised to OpenClaw (default: 8192)
  --dry-run           Validate and print actions without writing or deploying

VM/Compose options:
  --service-name NAME Docker Compose project name (default: llm-microservice)
  --install-dir PATH  VM stack directory (default: /opt/llm-microservice)
  --host ADDRESS      Bind address (default: 127.0.0.1)
  --port PORT         Published API port (default: 4000)
  --skip-docker-install
                      Require an existing Docker + Compose installation

Akash options:
  --akash-gpu-model MODEL  NVIDIA model requested when --gpu on (default: rtx4090)
  --akash-cpu UNITS        Ollama CPU units (default: 4)
  --akash-memory SIZE      Ollama memory (default: 16Gi)
  --akash-storage SIZE     Persistent model volume (default: 50Gi)
  --akash-max-price UAKT   Maximum price per block (default: 10000)

Examples:
  sudo bash install_llm_microservice.sh --platform vm --host 0.0.0.0
  bash install_llm_microservice.sh --platform compose --output-dir ./deployment
  bash install_llm_microservice.sh --akash --gpu on --akash-gpu-model rtx4090
  bash install_llm_microservice.sh --akash --with-openclaw
EOF
}

log() { printf '%s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

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
      --platform) PLATFORM="${2:?missing value for --platform}"; shift 2 ;;
      --akash) PLATFORM="akash"; shift ;;
      --service-name) SERVICE_NAME="${2:?missing value for --service-name}"; shift 2 ;;
      --install-dir) INSTALL_DIR="${2:?missing value for --install-dir}"; shift 2 ;;
      --output-dir) OUTPUT_DIR="${2:?missing value for --output-dir}"; shift 2 ;;
      --model) MODEL="${2:?missing value for --model}"; shift 2 ;;
      --model-alias) MODEL_ALIAS="${2:?missing value for --model-alias}"; shift 2 ;;
      --host) HOST="${2:?missing value for --host}"; shift 2 ;;
      --port) PORT="${2:?missing value for --port}"; shift 2 ;;
      --master-key) LITELLM_MASTER_KEY="${2:?missing value for --master-key}"; shift 2 ;;
      --gpu) GPU_MODE="${2:?missing value for --gpu}"; shift 2 ;;
      --litellm-image) LITELLM_IMAGE="${2:?missing value for --litellm-image}"; shift 2 ;;
      --ollama-image) OLLAMA_IMAGE="${2:?missing value for --ollama-image}"; shift 2 ;;
      --akash-gpu-model) AKASH_GPU_MODEL="${2:?missing value for --akash-gpu-model}"; shift 2 ;;
      --akash-cpu) AKASH_CPU="${2:?missing value for --akash-cpu}"; shift 2 ;;
      --akash-memory) AKASH_MEMORY="${2:?missing value for --akash-memory}"; shift 2 ;;
      --akash-storage) AKASH_MODEL_STORAGE="${2:?missing value for --akash-storage}"; shift 2 ;;
      --akash-max-price) AKASH_MAX_PRICE="${2:?missing value for --akash-max-price}"; shift 2 ;;
      --skip-docker-install) SKIP_DOCKER_INSTALL=1; shift ;;
      --skip-model) SKIP_MODEL=1; shift ;;
      --with-openclaw) WITH_OPENCLAW=1; shift ;;
      --openclaw-base-url) OPENCLAW_BASE_URL="${2:?missing value for --openclaw-base-url}"; shift 2 ;;
      --openclaw-agent-id) OPENCLAW_AGENT_ID="${2:?missing value for --openclaw-agent-id}"; shift 2 ;;
      --openclaw-context-window) OPENCLAW_CONTEXT_WINDOW="${2:?missing value for --openclaw-context-window}"; shift 2 ;;
      --openclaw-max-tokens) OPENCLAW_MAX_TOKENS="${2:?missing value for --openclaw-max-tokens}"; shift 2 ;;
      --dry-run) DRY_RUN=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) fail "unknown option: $1" ;;
    esac
  done
}

ensure_master_key() {
  [[ -n "$LITELLM_MASTER_KEY" ]] && return
  if [[ "$DRY_RUN" -eq 1 ]]; then
    LITELLM_MASTER_KEY="sk-dry-run-placeholder"
    log "[dry-run] generate a random LiteLLM master key"
  elif command -v openssl >/dev/null 2>&1; then
    LITELLM_MASTER_KEY="sk-$(openssl rand -hex 24)"
    log "Generated a random LiteLLM master key; it is stored only in the protected deployment files."
  else
    fail "set LITELLM_MASTER_KEY or install openssl so a key can be generated"
  fi
}

validate_settings() {
  [[ "$PLATFORM" =~ ^(vm|compose|akash)$ ]] || fail "platform must be one of: vm, compose, akash"
  [[ "$SERVICE_NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || fail "invalid service name"
  [[ "$MODEL_ALIAS" =~ ^[a-zA-Z0-9][a-zA-Z0-9._/-]*$ ]] || fail "model alias contains unsupported characters"
  [[ "$MODEL" =~ ^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$ ]] || fail "model contains unsupported characters"
  [[ "$HOST" =~ ^[a-zA-Z0-9._-]+$ ]] || fail "host contains unsupported characters"
  [[ "$PORT" =~ ^[0-9]+$ ]] && ((PORT >= 1 && PORT <= 65535)) || fail "port must be between 1 and 65535"
  [[ "$GPU_MODE" =~ ^(auto|on|off)$ ]] || fail "GPU mode must be one of: auto, on, off"
  [[ "$LITELLM_IMAGE" =~ ^[a-zA-Z0-9][a-zA-Z0-9._:/@-]*$ ]] || fail "invalid LiteLLM image"
  [[ "$OLLAMA_IMAGE" =~ ^[a-zA-Z0-9][a-zA-Z0-9._:/@-]*$ ]] || fail "invalid Ollama image"
  [[ "$LITELLM_MASTER_KEY" =~ ^sk-[a-zA-Z0-9._-]{12,}$ ]] || fail "master key must start with sk- and contain at least 12 safe characters"
  [[ "$AKASH_GPU_MODEL" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] || fail "invalid Akash GPU model"
  [[ "$AKASH_CPU" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail "Akash CPU must be numeric"
  [[ "$AKASH_MEMORY" =~ ^[0-9]+(Mi|Gi)$ ]] || fail "Akash memory must use Mi or Gi"
  [[ "$AKASH_MODEL_STORAGE" =~ ^[0-9]+(Mi|Gi|Ti)$ ]] || fail "Akash storage must use Mi, Gi, or Ti"
  [[ "$AKASH_MAX_PRICE" =~ ^[0-9]+$ ]] || fail "Akash maximum price must be an integer in uakt"
  [[ "$WITH_OPENCLAW" =~ ^[01]$ ]] || fail "WITH_OPENCLAW must be 0 or 1"
  [[ "$OPENCLAW_AGENT_ID" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || fail "invalid OpenClaw agent id"
  [[ "$OPENCLAW_CONTEXT_WINDOW" =~ ^[0-9]+$ ]] && ((OPENCLAW_CONTEXT_WINDOW >= 1024)) ||
    fail "OpenClaw context window must be an integer of at least 1024"
  [[ "$OPENCLAW_MAX_TOKENS" =~ ^[0-9]+$ ]] && ((OPENCLAW_MAX_TOKENS >= 1)) ||
    fail "OpenClaw max tokens must be a positive integer"
  ((OPENCLAW_MAX_TOKENS <= OPENCLAW_CONTEXT_WINDOW)) ||
    fail "OpenClaw max tokens cannot exceed the context window"
  if [[ -n "$OPENCLAW_BASE_URL" ]]; then
    [[ "$OPENCLAW_BASE_URL" =~ ^https?://[^[:space:]\"\\]+$ ]] || fail "invalid OpenClaw LiteLLM base URL"
    [[ "$OPENCLAW_BASE_URL" != */v1 ]] || fail "OpenClaw base URL must be the LiteLLM origin without /v1"
  fi
}

openclaw_base_url() {
  if [[ -n "$OPENCLAW_BASE_URL" ]]; then
    printf '%s' "$OPENCLAW_BASE_URL"
  elif [[ "$PLATFORM" == "akash" ]]; then
    printf '%s' "https://akash-litellm.example"
  elif [[ "$HOST" == "0.0.0.0" ]]; then
    printf '%s' "http://llm-host.example:${PORT}"
  else
    printf 'http://%s:%s' "$HOST" "$PORT"
  fi
}

write_openclaw_client_files() {
  local destination="$1"
  local base_url
  [[ "$WITH_OPENCLAW" -eq 1 ]] || return
  base_url="$(openclaw_base_url)"
  cat >"$destination/openclaw-litellm.json5" <<EOF
{
  models: {
    mode: "merge",
    providers: {
      litellm: {
        baseUrl: "${base_url}",
        apiKey: "\${LITELLM_API_KEY}",
        api: "openai-completions",
        models: [
          {
            id: "${MODEL_ALIAS}",
            name: "Sovereign ${MODEL_ALIAS}",
            reasoning: false,
            input: ["text"],
            contextWindow: ${OPENCLAW_CONTEXT_WINDOW},
            maxTokens: ${OPENCLAW_MAX_TOKENS},
          },
        ],
      },
    },
  },
  agents: {
    defaults: {
      model: { primary: "litellm/${MODEL_ALIAS}" },
    },
    list: [
      {
        id: "${OPENCLAW_AGENT_ID}",
        default: true,
        name: "Sovereign LiteLLM Agent",
        model: { primary: "litellm/${MODEL_ALIAS}", fallbacks: [] },
      },
    ],
  },
}
EOF
  printf 'LITELLM_API_KEY=%s\n' "$LITELLM_MASTER_KEY" >"$destination/openclaw.env"
  chmod 0640 "$destination/openclaw-litellm.json5" 2>/dev/null || true
  chmod 0600 "$destination/openclaw.env" 2>/dev/null ||
    log "Warning: protect ${destination}/openclaw.env with filesystem ACLs." >&2
}

as_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then "$@"; else sudo "$@"; fi
}

install_docker_if_needed() {
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 && return
  [[ "$SKIP_DOCKER_INSTALL" -eq 0 ]] || fail "Docker with the Compose plugin is required"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] install Docker Engine and the Compose plugin when absent"
    return
  fi
  [[ -r /etc/os-release ]] || fail "cannot identify the Linux distribution"
  # shellcheck disable=SC1091
  source /etc/os-release
  [[ "${ID:-}" =~ ^(debian|ubuntu)$ ]] || fail "automatic Docker installation supports Debian and Ubuntu only"
  run_cmd as_root apt-get update
  run_cmd as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-v2 ca-certificates curl
  run_cmd as_root systemctl enable --now docker
}

docker_cmd() {
  if docker info >/dev/null 2>&1; then docker "$@"; else as_root docker "$@"; fi
}

compose_cmd() {
  docker_cmd compose --project-name "$SERVICE_NAME" --project-directory "$INSTALL_DIR" "$@"
}

gpu_compose_block() {
  case "$GPU_MODE" in
    off) return ;;
    on)
      if [[ "$PLATFORM" == "vm" ]]; then
        command -v nvidia-smi >/dev/null 2>&1 && command -v nvidia-container-cli >/dev/null 2>&1 ||
          fail "GPU mode requires an NVIDIA driver and NVIDIA Container Toolkit"
      fi
      ;;
    auto)
      if [[ "$PLATFORM" == "compose" ]]; then
        log "Portable Compose is declarative: --gpu auto maps to CPU. Use --gpu on for a GPU target." >&2
        return
      fi
      if ! command -v nvidia-smi >/dev/null 2>&1 || ! command -v nvidia-container-cli >/dev/null 2>&1; then
        log "NVIDIA container runtime not detected; using CPU mode." >&2
        return
      fi
      ;;
  esac
  cat <<'EOF'
    gpus: all
EOF
}

write_compose_source() {
  local destination="$1"
  mkdir -p "$destination"
  cat >"$destination/config.yaml" <<EOF
model_list:
  - model_name: "${MODEL_ALIAS}"
    litellm_params:
      model: "ollama/${MODEL}"
      api_base: "http://ollama:11434"

general_settings:
  master_key: "os.environ/LITELLM_MASTER_KEY"
EOF
  printf 'LITELLM_MASTER_KEY=%s\n' "$LITELLM_MASTER_KEY" >"$destination/.env"
  chmod 0600 "$destination/.env"
  cat >"$destination/compose.yaml" <<EOF
services:
  ollama:
    image: "${OLLAMA_IMAGE}"
    restart: unless-stopped
    volumes:
      - ollama-data:/root/.ollama
$(gpu_compose_block)
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 10s
      timeout: 5s
      retries: 12

  litellm:
    image: "${LITELLM_IMAGE}"
    restart: unless-stopped
    env_file: [.env]
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    command: ["--config", "/app/config.yaml", "--port", "4000"]
    ports:
      - "${HOST}:${PORT}:4000"
    depends_on:
      ollama:
        condition: service_healthy

volumes:
  ollama-data:
EOF
  write_openclaw_client_files "$destination"
}

render_compose() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  write_compose_source "$temp_dir"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] write ${OUTPUT_DIR}/{compose.yaml,config.yaml,.env}"
    [[ "$WITH_OPENCLAW" -eq 0 ]] || log "[dry-run] write ${OUTPUT_DIR}/{openclaw-litellm.json5,openclaw.env}"
    rm -rf "$temp_dir"
    return
  fi
  mkdir -p "$OUTPUT_DIR"
  cp "$temp_dir/compose.yaml" "$OUTPUT_DIR/compose.yaml"
  cp "$temp_dir/config.yaml" "$OUTPUT_DIR/config.yaml"
  cp "$temp_dir/.env" "$OUTPUT_DIR/.env"
  if [[ "$WITH_OPENCLAW" -eq 1 ]]; then
    cp "$temp_dir/openclaw-litellm.json5" "$OUTPUT_DIR/openclaw-litellm.json5"
    cp "$temp_dir/openclaw.env" "$OUTPUT_DIR/openclaw.env"
  fi
  chmod 0750 "$OUTPUT_DIR" 2>/dev/null || log "Warning: set restrictive ACLs on ${OUTPUT_DIR}." >&2
  chmod 0640 "$OUTPUT_DIR/compose.yaml" "$OUTPUT_DIR/config.yaml" 2>/dev/null || true
  chmod 0600 "$OUTPUT_DIR/.env" 2>/dev/null || log "Warning: protect ${OUTPUT_DIR}/.env with filesystem ACLs." >&2
  [[ "$WITH_OPENCLAW" -eq 0 ]] || chmod 0600 "$OUTPUT_DIR/openclaw.env" 2>/dev/null ||
    log "Warning: protect ${OUTPUT_DIR}/openclaw.env with filesystem ACLs." >&2
  rm -rf "$temp_dir"
  log "Portable Compose bundle generated in ${OUTPUT_DIR}."
  log "Start it with: cd ${OUTPUT_DIR} && docker compose -p ${SERVICE_NAME} up -d"
}

render_vm() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  write_compose_source "$temp_dir"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] write ${INSTALL_DIR}/{compose.yaml,config.yaml,.env}"
    [[ "$WITH_OPENCLAW" -eq 0 ]] || log "[dry-run] write ${INSTALL_DIR}/{openclaw-litellm.json5,openclaw.env}"
    rm -rf "$temp_dir"
    return
  fi
  as_root install -d -m 0750 "$INSTALL_DIR"
  as_root install -m 0640 "$temp_dir/compose.yaml" "$INSTALL_DIR/compose.yaml"
  as_root install -m 0640 "$temp_dir/config.yaml" "$INSTALL_DIR/config.yaml"
  as_root install -m 0600 "$temp_dir/.env" "$INSTALL_DIR/.env"
  if [[ "$WITH_OPENCLAW" -eq 1 ]]; then
    as_root install -m 0640 "$temp_dir/openclaw-litellm.json5" "$INSTALL_DIR/openclaw-litellm.json5"
    as_root install -m 0600 "$temp_dir/openclaw.env" "$INSTALL_DIR/openclaw.env"
  fi
  rm -rf "$temp_dir"
}

akash_gpu_block() {
  [[ "$GPU_MODE" == "on" ]] || return
  cat <<EOF
        gpu:
          units: 1
          attributes:
            vendor:
              nvidia:
                - model: ${AKASH_GPU_MODEL}
EOF
}

akash_ollama_command() {
  if [[ "$SKIP_MODEL" -eq 1 ]]; then
    cat <<'EOF'
      - "exec ollama serve"
EOF
  else
    cat <<'EOF'
      - |
        ollama serve &
        server_pid=$!
        until ollama list >/dev/null 2>&1; do sleep 2; done
        ollama pull "$OLLAMA_MODEL"
        wait "$server_pid"
EOF
  fi
}

write_akash_sdl() {
  local path="$1"
  cat >"$path" <<EOF
version: "2.0"

services:
  ollama:
    image: "${OLLAMA_IMAGE}"
    env:
      - "OLLAMA_MODEL=${MODEL}"
    command: ["/bin/sh", "-c"]
    args:
$(akash_ollama_command)
    expose:
      - port: 11434
        to:
          - service: litellm
    params:
      storage:
        models:
          mount: /root/.ollama
          readOnly: false

  litellm:
    image: "${LITELLM_IMAGE}"
    env:
      - "LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY}"
    command: ["/bin/sh", "-c"]
    args:
      - |
        cat >/tmp/litellm-config.yaml <<'CONFIG'
        model_list:
          - model_name: "${MODEL_ALIAS}"
            litellm_params:
              model: "ollama/${MODEL}"
              api_base: "http://ollama:11434"
        general_settings:
          master_key: "os.environ/LITELLM_MASTER_KEY"
        CONFIG
        exec litellm --config /tmp/litellm-config.yaml --port 4000
    expose:
      - port: 4000
        as: 4000
        to:
          - global: true
        http_options:
          max_body_size: 10485760
          read_timeout: 60000
          send_timeout: 60000

profiles:
  compute:
    ollama:
      resources:
        cpu:
          units: ${AKASH_CPU}
        memory:
          size: ${AKASH_MEMORY}
        storage:
          - size: 2Gi
          - name: models
            size: ${AKASH_MODEL_STORAGE}
            attributes:
              persistent: true
              class: beta3
$(akash_gpu_block)
    litellm:
      resources:
        cpu:
          units: 0.5
        memory:
          size: 1Gi
        storage:
          - size: 1Gi
  placement:
    akash:
      pricing:
        ollama:
          denom: uakt
          amount: ${AKASH_MAX_PRICE}
        litellm:
          denom: uakt
          amount: 1000

deployment:
  ollama:
    akash:
      profile: ollama
      count: 1
  litellm:
    akash:
      profile: litellm
      count: 1
EOF
  chmod 0600 "$path"
}

render_akash() {
  if [[ "$GPU_MODE" == "auto" ]]; then
    GPU_MODE="off"
    log "Akash is declarative: --gpu auto maps to CPU. Use --gpu on to request NVIDIA hardware."
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] write protected Akash SDL to ${OUTPUT_DIR}/deploy.yaml"
    return
  fi
  mkdir -p "$OUTPUT_DIR"
  chmod 0700 "$OUTPUT_DIR" 2>/dev/null || log "Warning: set restrictive ACLs on ${OUTPUT_DIR}." >&2
  write_akash_sdl "$OUTPUT_DIR/deploy.yaml"
  write_openclaw_client_files "$OUTPUT_DIR"
  cat <<EOF
Akash deployment bundle generated: ${OUTPUT_DIR}/deploy.yaml

Deploy it:
  1. Open https://console.akash.network/deployments
  2. Choose "Build your template" and upload deploy.yaml
  3. Review bids, select a provider, then create the lease

The SDL contains the API key and is mode 0600. Do not commit or share it.
After deployment, use the LiteLLM service URI shown by Akash and append /v1.
EOF
  if [[ "$WITH_OPENCLAW" -eq 1 ]]; then
    log "OpenClaw client files generated. Replace akash-litellm.example with the lease URI."
  fi
}

wait_for_service() {
  local health_host="$HOST"
  [[ "$DRY_RUN" -eq 0 ]] || return 0
  [[ "$HOST" == "0.0.0.0" ]] && health_host="127.0.0.1"
  for _ in {1..60}; do
    if curl --fail --silent -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" "http://${health_host}:${PORT}/v1/models" >/dev/null; then
      log "LiteLLM is ready."
      return
    fi
    sleep 2
  done
  compose_cmd logs --tail 100 >&2 || true
  fail "LiteLLM did not become ready in time"
}

pull_model_vm() {
  if [[ "$SKIP_MODEL" -eq 1 ]]; then log "Model pull skipped."; return; fi
  if [[ "$DRY_RUN" -eq 1 ]]; then log "[dry-run] docker compose exec ollama ollama pull ${MODEL}"; return 0; fi
  compose_cmd exec -T ollama ollama pull "$MODEL"
}

print_vm_summary() {
  local public_host="$HOST"
  [[ "$HOST" == "0.0.0.0" ]] && public_host="<vm-ip>"
  cat <<EOF

LLM microservice installed.
API base URL: http://${public_host}:${PORT}/v1
Model: ${MODEL_ALIAS} (Ollama ${MODEL})
Stack directory: ${INSTALL_DIR}

Test with an OpenAI-compatible client using the generated master key stored in ${INSTALL_DIR}/.env.
EOF
  if [[ "$WITH_OPENCLAW" -eq 1 ]]; then
    log "OpenClaw client configuration: ${INSTALL_DIR}/openclaw-litellm.json5"
    log "OpenClaw client environment: ${INSTALL_DIR}/openclaw.env"
  fi
  [[ "$HOST" != "0.0.0.0" ]] || log "Security: restrict TCP/${PORT} and terminate TLS in front of the API."
}

deploy_vm() {
  if [[ "$DRY_RUN" -eq 0 ]]; then
    command -v sudo >/dev/null 2>&1 || [[ "${EUID:-$(id -u)}" -eq 0 ]] || fail "run as root or install sudo"
  fi
  install_docker_if_needed
  [[ "$DRY_RUN" -eq 1 ]] || command -v curl >/dev/null 2>&1 || fail "curl is required"
  render_vm
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "[dry-run] docker compose pull"
    log "[dry-run] docker compose up -d"
  else
    compose_cmd pull
    compose_cmd up -d
  fi
  pull_model_vm
  wait_for_service
  print_vm_summary
}

main() {
  parse_args "$@"
  ensure_master_key
  validate_settings
  case "$PLATFORM" in
    vm) deploy_vm ;;
    compose) render_compose ;;
    akash) render_akash ;;
  esac
}

main "$@"
