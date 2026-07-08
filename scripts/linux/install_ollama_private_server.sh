#!/usr/bin/env bash
set -Eeuo pipefail

# Install and configure Ollama on a private Linux server.
# Defaults are conservative: bind only to localhost and do not open firewall ports.
#
# Examples:
#   sudo bash install_ollama_private_server.sh
#   sudo bash install_ollama_private_server.sh --model llama3.1:8b
#   sudo bash install_ollama_private_server.sh --listen-lan --allow-cidr 10.0.0.0/8
#   sudo bash install_ollama_private_server.sh --host 0.0.0.0 --port 11434 --open-firewall
#   sudo bash install_ollama_private_server.sh --install-openwebui --webui-bind 127.0.0.1 --webui-port 3000
#   sudo bash install_ollama_private_server.sh --install-openwebui --webui-bind 0.0.0.0 --open-webui-firewall --allow-cidr 10.0.0.0/8
#   sudo bash install_ollama_private_server.sh --dry-run --install-openwebui --model-profile gpu24
#   sudo bash install_ollama_private_server.sh --update --install-openwebui
#   sudo bash install_ollama_private_server.sh --uninstall

MODEL="llama3.1:8b"
MODEL_PROFILE="default"
HOST="127.0.0.1"
PORT="11434"
MODELS_DIR="/var/lib/ollama/models"
OPEN_FIREWALL="false"
ALLOW_CIDR=""
PULL_MODEL="true"
INSTALL_ONLY="false"
API_CHECK_HOST="127.0.0.1"
INSTALL_OPENWEBUI="false"
WEBUI_BIND="127.0.0.1"
WEBUI_PORT="3000"
WEBUI_IMAGE="ghcr.io/open-webui/open-webui:main"
WEBUI_CONTAINER="open-webui"
WEBUI_VOLUME="open-webui"
WEBUI_AUTH="true"
WEBUI_SECRET_KEY=""
OPEN_WEBUI_FIREWALL="false"
OLLAMA_HOST_WAS_DEFAULT="true"
DRY_RUN="false"
ACTION="install"
PURGE_DATA="false"
BACKUP="false"
BACKUP_DIR=""
BLOCK_OLLAMA_PUBLIC="false"
AUTO_BLOCK_OLLAMA_PUBLIC="false"
WEBUI_CUDA="auto"
GPU_AVAILABLE="false"
TEST_GENERATION="true"
TEST_PROMPT="Reponds seulement par: ok"

usage() {
  cat <<'EOF'
Usage: sudo bash install_ollama_private_server.sh [options]

Options:
  --dry-run            Print the planned install/update/uninstall actions and exit.
  --update             Update Ollama and, when selected, recreate Open WebUI.
  --uninstall          Stop/disable Ollama and remove Open WebUI container.
  --purge-data         With --uninstall, also remove local model and WebUI data.
  --backup             Create a backup before update or uninstall.
  --backup-dir PATH    Backup destination. Default: /root/ollama-backup-YYYYmmdd-HHMMSS
  --model NAME          Model to pull after install. Default: llama3.1:8b
  --model-profile NAME  Choose a model preset: small, default, gpu24, gpu48.
  --no-pull            Install Ollama but do not pull a model.
  --host ADDR          Address for Ollama to bind. Default: 127.0.0.1
  --port PORT          Port for Ollama. Default: 11434
  --listen-lan         Shortcut for --host 0.0.0.0
  --models-dir PATH    Model storage directory. Default: /var/lib/ollama/models
  --open-firewall      Open the Ollama port with ufw or firewalld.
  --allow-cidr CIDR    Restrict firewall allow rule to a CIDR when supported.
  --install-openwebui  Install Open WebUI in Docker and connect it to Ollama.
  --webui-bind ADDR    Address for Open WebUI to bind. Default: 127.0.0.1
  --webui-port PORT    Host port for Open WebUI. Default: 3000
  --webui-image IMAGE  Open WebUI image. Default: ghcr.io/open-webui/open-webui:main
  --webui-no-auth      Disable Open WebUI login. Not recommended except for trusted local-only use.
  --webui-secret KEY   Persistent WEBUI_SECRET_KEY. Generated automatically if omitted.
  --webui-cuda MODE    Open WebUI CUDA image mode: auto, on, off. Default: auto.
  --open-webui-firewall
                        Open the Open WebUI port with ufw or firewalld.
  --block-ollama-public
                        Add a deny/remove firewall rule for Ollama's API port.
  --no-test-generation Skip the final short generation test.
  --test-prompt TEXT   Prompt for the final generation test.
  --install-only       Install and configure service, skip health/model checks.
  -h, --help           Show this help.

Security note:
  Ollama's HTTP API has no built-in authentication. For a private server,
  prefer HOST=127.0.0.1 with SSH tunneling, VPN, or a reverse proxy that adds TLS
  and authentication. Use --listen-lan only on a trusted private network.
EOF
}

log() {
  printf '\n[ollama-install] %s\n' "$*"
}

die() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

print_plan() {
  cat <<EOF
Planned Ollama private server action:
  Action: ${ACTION}
  Model profile: ${MODEL_PROFILE}
  Model: ${MODEL}
  Pull model: ${PULL_MODEL}
  Ollama bind: ${HOST}:${PORT}
  Models directory: ${MODELS_DIR}
  Open Ollama firewall: ${OPEN_FIREWALL}
  Block public Ollama API: ${BLOCK_OLLAMA_PUBLIC}
  Allow CIDR: ${ALLOW_CIDR:-not set}

Open WebUI:
  Install/recreate: ${INSTALL_OPENWEBUI}
  Bind: ${WEBUI_BIND}:${WEBUI_PORT}
  Image: ${WEBUI_IMAGE}
  CUDA mode: ${WEBUI_CUDA}
  Auth enabled: ${WEBUI_AUTH}
  Open WebUI firewall: ${OPEN_WEBUI_FIREWALL}

Maintenance:
  Backup: ${BACKUP}
  Backup dir: ${BACKUP_DIR:-auto}
  Purge data on uninstall: ${PURGE_DATA}
  Test generation: ${TEST_GENERATION}
EOF
}

apply_model_profile() {
  case "$MODEL_PROFILE" in
    small)
      MODEL="llama3.2:3b"
      ;;
    default)
      [[ "$MODEL" == "llama3.1:8b" ]] || return 0
      MODEL="llama3.1:8b"
      ;;
    gpu24)
      MODEL="qwen2.5:14b"
      ;;
    gpu48)
      MODEL="qwen2.5:32b"
      ;;
    custom)
      ;;
    *)
      die "Unknown model profile: ${MODEL_PROFILE}. Use small, default, gpu24, gpu48, or custom."
      ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    --update)
      ACTION="update"
      shift
      ;;
    --uninstall)
      ACTION="uninstall"
      shift
      ;;
    --purge-data)
      PURGE_DATA="true"
      shift
      ;;
    --backup)
      BACKUP="true"
      shift
      ;;
    --backup-dir)
      BACKUP_DIR="${2:-}"
      [[ -n "$BACKUP_DIR" ]] || die "--backup-dir requires a value"
      shift 2
      ;;
    --model)
      MODEL="${2:-}"
      [[ -n "$MODEL" ]] || die "--model requires a value"
      MODEL_PROFILE="custom"
      shift 2
      ;;
    --model-profile)
      MODEL_PROFILE="${2:-}"
      [[ -n "$MODEL_PROFILE" ]] || die "--model-profile requires a value"
      shift 2
      ;;
    --no-pull)
      PULL_MODEL="false"
      shift
      ;;
    --host)
      HOST="${2:-}"
      [[ -n "$HOST" ]] || die "--host requires a value"
      OLLAMA_HOST_WAS_DEFAULT="false"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      [[ "$PORT" =~ ^[0-9]+$ ]] || die "--port must be numeric"
      shift 2
      ;;
    --listen-lan)
      HOST="0.0.0.0"
      OLLAMA_HOST_WAS_DEFAULT="false"
      shift
      ;;
    --models-dir)
      MODELS_DIR="${2:-}"
      [[ -n "$MODELS_DIR" ]] || die "--models-dir requires a value"
      shift 2
      ;;
    --open-firewall)
      OPEN_FIREWALL="true"
      shift
      ;;
    --allow-cidr)
      ALLOW_CIDR="${2:-}"
      [[ -n "$ALLOW_CIDR" ]] || die "--allow-cidr requires a value"
      shift 2
      ;;
    --install-openwebui)
      INSTALL_OPENWEBUI="true"
      shift
      ;;
    --webui-bind)
      WEBUI_BIND="${2:-}"
      [[ -n "$WEBUI_BIND" ]] || die "--webui-bind requires a value"
      shift 2
      ;;
    --webui-port)
      WEBUI_PORT="${2:-}"
      [[ "$WEBUI_PORT" =~ ^[0-9]+$ ]] || die "--webui-port must be numeric"
      shift 2
      ;;
    --webui-image)
      WEBUI_IMAGE="${2:-}"
      [[ -n "$WEBUI_IMAGE" ]] || die "--webui-image requires a value"
      shift 2
      ;;
    --webui-no-auth)
      WEBUI_AUTH="false"
      shift
      ;;
    --webui-secret)
      WEBUI_SECRET_KEY="${2:-}"
      [[ -n "$WEBUI_SECRET_KEY" ]] || die "--webui-secret requires a value"
      shift 2
      ;;
    --webui-cuda)
      WEBUI_CUDA="${2:-}"
      [[ "$WEBUI_CUDA" =~ ^(auto|on|off)$ ]] || die "--webui-cuda must be one of: auto, on, off"
      shift 2
      ;;
    --open-webui-firewall)
      OPEN_WEBUI_FIREWALL="true"
      shift
      ;;
    --block-ollama-public)
      BLOCK_OLLAMA_PUBLIC="true"
      shift
      ;;
    --no-test-generation)
      TEST_GENERATION="false"
      shift
      ;;
    --test-prompt)
      TEST_PROMPT="${2:-}"
      [[ -n "$TEST_PROMPT" ]] || die "--test-prompt requires a value"
      shift 2
      ;;
    --install-only)
      INSTALL_ONLY="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

apply_model_profile

if [[ "$INSTALL_OPENWEBUI" == "true" && "$WEBUI_CUDA" == "on" && "$WEBUI_IMAGE" == "ghcr.io/open-webui/open-webui:main" ]]; then
  WEBUI_IMAGE="ghcr.io/open-webui/open-webui:cuda"
fi

if [[ "$INSTALL_OPENWEBUI" == "true" && "$OLLAMA_HOST_WAS_DEFAULT" == "true" ]]; then
  HOST="0.0.0.0"
  if [[ "$OPEN_FIREWALL" != "true" && "$BLOCK_OLLAMA_PUBLIC" != "true" ]]; then
    BLOCK_OLLAMA_PUBLIC="true"
    AUTO_BLOCK_OLLAMA_PUBLIC="true"
  fi
fi

if [[ "$DRY_RUN" == "true" ]]; then
  print_plan
  exit 0
fi

if [[ "${EUID}" -ne 0 ]]; then
  die "Run as root, for example: sudo bash $0"
fi

if ! command -v systemctl >/dev/null 2>&1; then
  die "This script expects a systemd-based Linux server."
fi

if [[ "$HOST" == "0.0.0.0" && "$OPEN_FIREWALL" != "true" ]]; then
  log "Ollama will listen on all interfaces, but firewall changes are disabled."
  log "Make sure the server is protected by VPN, security group rules, or a reverse proxy with auth."
fi

if [[ "$INSTALL_OPENWEBUI" == "true" && "$OLLAMA_HOST_WAS_DEFAULT" == "true" ]]; then
  log "Open WebUI requested: setting Ollama bind to 0.0.0.0 so the Docker container can reach it."
  if [[ "$AUTO_BLOCK_OLLAMA_PUBLIC" == "true" ]]; then
    log "The script will also add a defensive firewall block for Ollama's API port."
  else
    log "The script will not open Ollama's firewall port unless --open-firewall is also set."
  fi
fi

install_prereqs() {
  log "Installing basic prerequisites"
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y curl ca-certificates openssl
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y curl ca-certificates openssl
  elif command -v yum >/dev/null 2>&1; then
    yum install -y curl ca-certificates openssl
  elif command -v zypper >/dev/null 2>&1; then
    zypper --non-interactive install curl ca-certificates openssl
  elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache curl ca-certificates openssl
  else
    command -v curl >/dev/null 2>&1 || die "curl is required and no supported package manager was found"
  fi
}

install_docker_if_needed() {
  [[ "$INSTALL_OPENWEBUI" == "true" ]] || return 0
  if command -v docker >/dev/null 2>&1; then
    return 0
  fi

  log "Installing Docker for Open WebUI"
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y docker
  elif command -v yum >/dev/null 2>&1; then
    yum install -y docker
  elif command -v zypper >/dev/null 2>&1; then
    zypper --non-interactive install docker
  elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache docker
  else
    die "Docker is required for Open WebUI. Install Docker, then rerun this script."
  fi
}

detect_gpu() {
  GPU_AVAILABLE="false"
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    GPU_AVAILABLE="true"
    log "NVIDIA GPU detected"
  else
    log "No NVIDIA GPU detected; Ollama will use CPU unless drivers are installed."
  fi

  if [[ "$INSTALL_OPENWEBUI" == "true" && "$WEBUI_CUDA" == "auto" && "$GPU_AVAILABLE" == "true" && "$WEBUI_IMAGE" == "ghcr.io/open-webui/open-webui:main" ]]; then
    WEBUI_IMAGE="ghcr.io/open-webui/open-webui:cuda"
    log "Open WebUI CUDA image selected automatically."
  fi
}

make_backup() {
  [[ "$BACKUP" == "true" ]] || return 0

  if [[ -z "$BACKUP_DIR" ]]; then
    BACKUP_DIR="/root/ollama-backup-$(date +%Y%m%d-%H%M%S)"
  fi

  log "Creating backup in ${BACKUP_DIR}"
  mkdir -p "$BACKUP_DIR"

  if [[ -d /etc/systemd/system/ollama.service.d ]]; then
    tar -C /etc/systemd/system -czf "${BACKUP_DIR}/ollama-systemd-dropins.tar.gz" ollama.service.d
  fi

  if [[ -d "$MODELS_DIR" ]]; then
    log "Backing up Ollama model directory metadata and files. This can be large."
    tar -czf "${BACKUP_DIR}/ollama-models.tar.gz" "$MODELS_DIR" || log "Model backup failed or was interrupted."
  fi

  if command -v docker >/dev/null 2>&1 && docker volume inspect "$WEBUI_VOLUME" >/dev/null 2>&1; then
    log "Backing up Open WebUI Docker volume"
    docker run --rm \
      -v "${WEBUI_VOLUME}:/data:ro" \
      -v "${BACKUP_DIR}:/backup" \
      busybox sh -c "cd /data && tar -czf /backup/open-webui-volume.tar.gz ." || log "Open WebUI volume backup failed."
  fi
}

install_ollama() {
  log "Installing Ollama with the official installer"
  curl -fsSL https://ollama.com/install.sh | sh
}

configure_service() {
  log "Configuring Ollama systemd service"
  id ollama >/dev/null 2>&1 || useradd -r -s /bin/false -U -m -d /usr/share/ollama ollama

  mkdir -p "$MODELS_DIR"
  chown -R ollama:ollama "$(dirname "$MODELS_DIR")"

  mkdir -p /etc/systemd/system/ollama.service.d
  cat >/etc/systemd/system/ollama.service.d/private-server.conf <<EOF
[Service]
Environment="OLLAMA_HOST=${HOST}:${PORT}"
Environment="OLLAMA_MODELS=${MODELS_DIR}"
EOF

  systemctl daemon-reload
  systemctl enable ollama
  systemctl restart ollama
}

configure_firewall() {
  [[ "$OPEN_FIREWALL" == "true" ]] || return 0

  log "Opening firewall for TCP port ${PORT}"
  if command -v ufw >/dev/null 2>&1; then
    if [[ -n "$ALLOW_CIDR" ]]; then
      ufw allow from "$ALLOW_CIDR" to any port "$PORT" proto tcp
    else
      ufw allow "$PORT/tcp"
    fi
  elif command -v firewall-cmd >/dev/null 2>&1; then
    if [[ -n "$ALLOW_CIDR" ]]; then
      firewall-cmd --permanent --new-zone=ollama-private >/dev/null 2>&1 || true
      firewall-cmd --permanent --zone=ollama-private --add-source="$ALLOW_CIDR"
      firewall-cmd --permanent --zone=ollama-private --add-port="${PORT}/tcp"
      firewall-cmd --reload
    else
      firewall-cmd --permanent --add-port="${PORT}/tcp"
      firewall-cmd --reload
    fi
  else
    log "No ufw or firewalld detected. Configure your cloud/security-group firewall manually."
  fi
}

block_ollama_public_firewall() {
  [[ "$BLOCK_OLLAMA_PUBLIC" == "true" ]] || return 0

  log "Adding defensive firewall block for Ollama TCP port ${PORT}"
  if command -v ufw >/dev/null 2>&1; then
    ufw deny "$PORT/tcp" || true
  elif command -v firewall-cmd >/dev/null 2>&1; then
    firewall-cmd --permanent --remove-port="${PORT}/tcp" >/dev/null 2>&1 || true
    firewall-cmd --reload || true
  else
    log "No ufw or firewalld detected. Block ${PORT}/tcp in your provider firewall/security group."
  fi
}

open_webui_firewall() {
  [[ "$INSTALL_OPENWEBUI" == "true" ]] || return 0
  [[ "$WEBUI_BIND" != "127.0.0.1" && "$WEBUI_BIND" != "localhost" ]] || return 0
  [[ "$OPEN_WEBUI_FIREWALL" == "true" ]] || return 0

  log "Opening firewall for Open WebUI TCP port ${WEBUI_PORT}"
  if command -v ufw >/dev/null 2>&1; then
    if [[ -n "$ALLOW_CIDR" ]]; then
      ufw allow from "$ALLOW_CIDR" to any port "$WEBUI_PORT" proto tcp
    else
      ufw allow "$WEBUI_PORT/tcp"
    fi
  elif command -v firewall-cmd >/dev/null 2>&1; then
    if [[ -n "$ALLOW_CIDR" ]]; then
      firewall-cmd --permanent --new-zone=ollama-private >/dev/null 2>&1 || true
      firewall-cmd --permanent --zone=ollama-private --add-source="$ALLOW_CIDR"
      firewall-cmd --permanent --zone=ollama-private --add-port="${WEBUI_PORT}/tcp"
      firewall-cmd --reload
    else
      firewall-cmd --permanent --add-port="${WEBUI_PORT}/tcp"
      firewall-cmd --reload
    fi
  else
    log "No ufw or firewalld detected. Configure your Open WebUI firewall manually."
  fi
}

wait_for_ollama() {
  log "Waiting for Ollama API"
  if [[ "$HOST" != "0.0.0.0" && "$HOST" != "::" ]]; then
    API_CHECK_HOST="$HOST"
  fi

  for _ in $(seq 1 30); do
    if curl -fsS "http://${API_CHECK_HOST}:${PORT}/api/tags" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  systemctl --no-pager --full status ollama || true
  journalctl -u ollama -n 80 --no-pager || true
  die "Ollama did not become ready on ${API_CHECK_HOST}:${PORT}"
}

pull_model() {
  [[ "$PULL_MODEL" == "true" ]] || return 0
  log "Pulling model: ${MODEL}"
  if command -v runuser >/dev/null 2>&1; then
    runuser -u ollama -- env OLLAMA_HOST="${API_CHECK_HOST}:${PORT}" ollama pull "$MODEL"
  elif command -v su >/dev/null 2>&1; then
    su -s /bin/sh ollama -c "OLLAMA_HOST='${API_CHECK_HOST}:${PORT}' ollama pull '${MODEL}'"
  else
    OLLAMA_HOST="${API_CHECK_HOST}:${PORT}" ollama pull "$MODEL"
  fi
}

generate_webui_secret() {
  [[ -n "$WEBUI_SECRET_KEY" ]] && return 0
  if command -v openssl >/dev/null 2>&1; then
    WEBUI_SECRET_KEY="$(openssl rand -hex 32)"
  else
    WEBUI_SECRET_KEY="$(date +%s)-change-this-open-webui-secret"
  fi
}

install_openwebui() {
  [[ "$INSTALL_OPENWEBUI" == "true" ]] || return 0

  log "Installing Open WebUI with Docker"
  systemctl enable docker >/dev/null 2>&1 || true
  systemctl start docker >/dev/null 2>&1 || true
  docker info >/dev/null 2>&1 || die "Docker is not running or not usable by root."

  generate_webui_secret

  local ollama_base_url
  if [[ "$HOST" == "0.0.0.0" || "$HOST" == "::" ]]; then
    ollama_base_url="http://host.docker.internal:${PORT}"
  else
    ollama_base_url="http://${HOST}:${PORT}"
  fi

  docker rm -f "$WEBUI_CONTAINER" >/dev/null 2>&1 || true
  docker pull "$WEBUI_IMAGE"

  local gpu_args=()
  if [[ "$WEBUI_CUDA" != "off" && "$GPU_AVAILABLE" == "true" ]]; then
    gpu_args=(--gpus all)
  elif [[ "$WEBUI_CUDA" == "on" && "$GPU_AVAILABLE" != "true" ]]; then
    log "CUDA mode was requested, but no NVIDIA GPU was detected. Continuing without --gpus all."
  fi

  docker run -d \
    --name "$WEBUI_CONTAINER" \
    --restart always \
    --add-host=host.docker.internal:host-gateway \
    "${gpu_args[@]}" \
    -p "${WEBUI_BIND}:${WEBUI_PORT}:8080" \
    -v "${WEBUI_VOLUME}:/app/backend/data" \
    -e "OLLAMA_BASE_URL=${ollama_base_url}" \
    -e "WEBUI_AUTH=${WEBUI_AUTH}" \
    -e "WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}" \
    "$WEBUI_IMAGE" >/dev/null

  wait_for_openwebui
}

wait_for_openwebui() {
  log "Waiting for Open WebUI"
  local webui_check_host="127.0.0.1"
  if [[ "$WEBUI_BIND" != "0.0.0.0" && "$WEBUI_BIND" != "::" && "$WEBUI_BIND" != "localhost" ]]; then
    webui_check_host="$WEBUI_BIND"
  fi

  for _ in $(seq 1 45); do
    if curl -fsS "http://${webui_check_host}:${WEBUI_PORT}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  docker logs --tail 120 "$WEBUI_CONTAINER" || true
  die "Open WebUI did not become ready on ${webui_check_host}:${WEBUI_PORT}"
}

test_generation() {
  [[ "$TEST_GENERATION" == "true" ]] || return 0
  [[ "$PULL_MODEL" == "true" ]] || return 0

  log "Running a short Ollama generation test with ${MODEL}"
  if command -v runuser >/dev/null 2>&1; then
    runuser -u ollama -- env OLLAMA_HOST="${API_CHECK_HOST}:${PORT}" ollama run "$MODEL" "$TEST_PROMPT"
  elif command -v su >/dev/null 2>&1; then
    su -s /bin/sh ollama -c "OLLAMA_HOST='${API_CHECK_HOST}:${PORT}' ollama run '${MODEL}' '${TEST_PROMPT}'"
  else
    OLLAMA_HOST="${API_CHECK_HOST}:${PORT}" ollama run "$MODEL" "$TEST_PROMPT"
  fi
}

uninstall_stack() {
  log "Uninstalling Ollama/Open WebUI services"
  make_backup

  if command -v docker >/dev/null 2>&1; then
    docker rm -f "$WEBUI_CONTAINER" >/dev/null 2>&1 || true
    if [[ "$PURGE_DATA" == "true" ]]; then
      docker volume rm "$WEBUI_VOLUME" >/dev/null 2>&1 || true
    fi
  fi

  systemctl disable --now ollama >/dev/null 2>&1 || true
  rm -rf /etc/systemd/system/ollama.service.d
  systemctl daemon-reload

  if [[ "$PURGE_DATA" == "true" ]]; then
    rm -rf "$MODELS_DIR" /usr/share/ollama
  fi

  log "Uninstall complete. Package/binary removal is distribution-specific; data purge was ${PURGE_DATA}."
}

update_stack() {
  log "Updating Ollama/Open WebUI stack"
  make_backup
  install_prereqs
  install_docker_if_needed
  detect_gpu
  install_ollama
  configure_service
  configure_firewall
  block_ollama_public_firewall

  if [[ "$INSTALL_ONLY" != "true" ]]; then
    wait_for_ollama
    pull_model
    install_openwebui
    open_webui_firewall
    test_generation
  fi

  print_summary
}

print_summary() {
  local public_hint
  public_hint="localhost only"
  if [[ "$HOST" == "0.0.0.0" ]]; then
    public_hint="network exposed on configured interfaces"
  fi

  cat <<EOF

Ollama installation complete.

Service:
  sudo systemctl status ollama
  journalctl -u ollama -f

API:
  Bind: ${HOST}:${PORT} (${public_hint})
  Local health check: curl http://127.0.0.1:${PORT}/api/tags

  Model:
  ${MODEL}
  Test: ollama run ${MODEL} "Bonjour, reponds en une phrase."

Open WebUI:
  Installed: ${INSTALL_OPENWEBUI}
  URL: http://${WEBUI_BIND}:${WEBUI_PORT}
  Image: ${WEBUI_IMAGE}
  GPU detected: ${GPU_AVAILABLE}
  Container logs: docker logs -f ${WEBUI_CONTAINER}
  Update: docker pull ${WEBUI_IMAGE} && docker rm -f ${WEBUI_CONTAINER} && rerun this script with --install-openwebui

Private access recommendation:
  Keep Ollama bound to 127.0.0.1 and connect with:
  ssh -L ${PORT}:127.0.0.1:${PORT} user@your-server
  For Open WebUI local-only access:
  ssh -L ${WEBUI_PORT}:127.0.0.1:${WEBUI_PORT} user@your-server

EOF
}

main() {
  case "$ACTION" in
    uninstall)
      uninstall_stack
      print_summary
      return 0
      ;;
    update)
      update_stack
      return 0
      ;;
    install)
      ;;
    *)
      die "Unknown action: ${ACTION}"
      ;;
  esac

  make_backup
  install_prereqs
  install_docker_if_needed
  detect_gpu
  install_ollama
  configure_service
  configure_firewall
  block_ollama_public_firewall

  if [[ "$INSTALL_ONLY" != "true" ]]; then
    wait_for_ollama
    pull_model
    install_openwebui
    open_webui_firewall
    test_generation
  fi

  print_summary
}

main "$@"
