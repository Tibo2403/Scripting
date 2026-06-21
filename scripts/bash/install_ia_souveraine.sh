#!/usr/bin/env bash

# =========================================================================
# SCRIPT D'INSTALLATION AUTOMATISÉE IA SOUVERAINE (NIVEAU 1)
# AUTOMATED SOVEREIGN AI INSTALLATION SCRIPT (LEVEL 1)
# Deploys: Open WebUI + Ollama all-in-one container with optional GPU support
# =========================================================================

set -Eeuo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

CONTAINER_NAME="${CONTAINER_NAME:-ia-souveraine}"
HOST_PORT="${HOST_PORT:-3000}"
WEBUI_VOLUME="${WEBUI_VOLUME:-open-webui}"
OLLAMA_VOLUME="${OLLAMA_VOLUME:-ollama}"
IMAGE="${IMAGE:-ghcr.io/open-webui/open-webui:ollama}"
GPU_MODE="${GPU_MODE:-auto}"

print_header() {
  echo -e "${BLUE}====================================================${NC}"
  echo -e "${BLUE}   [FR] INSTALLATION DE L'IA LOCALE SOUVERAINE      ${NC}"
  echo -e "${BLUE}   [EN] LOCAL SOVEREIGN AI INSTALLER               ${NC}"
  echo -e "${BLUE}====================================================${NC}"
}

info() {
  echo -e "${GREEN}$*${NC}"
}

warn() {
  echo -e "${YELLOW}$*${NC}"
}

error() {
  echo -e "${RED}$*${NC}" >&2
}

require_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    error "✘ [FR] Commande manquante: ${command_name}"
    error "✘ [EN] Missing command: ${command_name}"
    exit 1
  fi
}

docker_supports_gpu() {
  command -v nvidia-smi >/dev/null 2>&1 && docker info 2>/dev/null | grep -qi 'nvidia'
}

build_gpu_args() {
  case "${GPU_MODE}" in
    on)
      echo "--gpus all"
      ;;
    off)
      echo ""
      ;;
    auto)
      if docker_supports_gpu; then
        echo "--gpus all"
      else
        echo ""
      fi
      ;;
    *)
      error "✘ GPU_MODE must be one of: auto, on, off"
      exit 1
      ;;
  esac
}

container_exists() {
  docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"
}

container_running() {
  docker ps --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"
}

start_container() {
  info "\n[1/3] [FR] Lancement du conteneur Docker Open WebUI + Ollama..."
  info "[1/3] [EN] Launching Open WebUI + Ollama Docker container..."

  if container_running; then
    warn "[FR] Le conteneur ${CONTAINER_NAME} est déjà en cours d'exécution."
    warn "[EN] Container ${CONTAINER_NAME} is already running."
    return
  fi

  if container_exists; then
    warn "[FR] Le conteneur ${CONTAINER_NAME} existe déjà. Redémarrage..."
    warn "[EN] Container ${CONTAINER_NAME} already exists. Restarting..."
    docker start "${CONTAINER_NAME}" >/dev/null
    return
  fi

  local gpu_args
  gpu_args="$(build_gpu_args)"

  if [ -z "${gpu_args}" ]; then
    warn "[FR] Aucun GPU NVIDIA Docker détecté ou GPU désactivé. Démarrage en mode CPU."
    warn "[EN] No NVIDIA Docker GPU detected or GPU disabled. Starting in CPU mode."
  fi

  # shellcheck disable=SC2086
  docker run -d \
    -p "${HOST_PORT}:8080" \
    ${gpu_args} \
    --name "${CONTAINER_NAME}" \
    -v "${OLLAMA_VOLUME}:/root/.ollama" \
    -v "${WEBUI_VOLUME}:/app/backend/data" \
    --restart always \
    "${IMAGE}" >/dev/null

  info "✔ [FR] Conteneur démarré avec succès sur le port ${HOST_PORT}."
  info "✔ [EN] Container started successfully on port ${HOST_PORT}."
}

wait_for_ollama() {
  info "\n[2/3] [FR] Attente de l'initialisation d'Ollama..."
  info "[2/3] [EN] Waiting for Ollama initialization..."

  for attempt in {1..30}; do
    if docker exec "${CONTAINER_NAME}" ollama list >/dev/null 2>&1; then
      info "✔ [FR] Ollama est prêt."
      info "✔ [EN] Ollama is ready."
      return
    fi
    sleep 2
    printf '.'
  done

  echo
  error "✘ [FR] Ollama ne répond pas dans le conteneur."
  error "✘ [EN] Ollama is not responding inside the container."
  docker logs --tail 80 "${CONTAINER_NAME}" >&2 || true
  exit 1
}

pull_model() {
  local model="$1"
  info "\n[FR] Téléchargement du modèle ${model}..."
  info "[EN] Downloading model ${model}..."
  docker exec "${CONTAINER_NAME}" ollama pull "${model}"
}

select_model() {
  info "\n[3/3] [FR] Choisissez un modèle / [EN] Choose a model:"
  echo -e "${BLUE}----------------------------------------------------${NC}"
  echo "1) Qwen 2.5 Coder (7B)  -> [FR] Idéal Code/Logique | [EN] Best for Code/Logic"
  echo "2) Mistral (7B)         -> [FR] Excellent en Français | [EN] Great for French text"
  echo "3) Llama 3.1 (8B)       -> [FR] Modèle généraliste | [EN] General purpose model"
  echo "4) [FR] Installer les 3 / [EN] Install all 3 models"
  echo "5) [FR] Ne rien installer maintenant / [EN] Skip model installation"
  echo -e "${BLUE}----------------------------------------------------${NC}"
  read -r -p "Selection (1-5): " choice

  case "${choice}" in
    1)
      pull_model "qwen2.5-coder:7b"
      ;;
    2)
      pull_model "mistral:7b"
      ;;
    3)
      pull_model "llama3.1:8b"
      ;;
    4)
      pull_model "qwen2.5-coder:7b"
      pull_model "mistral:7b"
      pull_model "llama3.1:8b"
      ;;
    5)
      warn "[FR] Aucun modèle installé maintenant."
      warn "[EN] No model installed now."
      ;;
    *)
      warn "[FR] Choix invalide. Aucun modèle installé automatiquement."
      warn "[EN] Invalid choice. No model installed automatically."
      ;;
  esac
}

print_success() {
  echo -e "\n${GREEN}====================================================${NC}"
  echo -e "${GREEN}[FR] INSTALLATION TERMINÉE 🎉${NC}"
  echo -e "${GREEN}[EN] INSTALLATION COMPLETED 🎉${NC}"
  echo "URL: http://<SERVER-IP>:${HOST_PORT}"
  echo "Local URL: http://localhost:${HOST_PORT}"
  echo "[FR] Le premier compte créé sera l'administrateur."
  echo "[EN] The first account created will be the administrator."
  echo -e "${GREEN}====================================================${NC}"
}

main() {
  print_header
  require_command docker

  if ! docker info >/dev/null 2>&1; then
    error "✘ [FR] Docker n'est pas disponible ou le daemon n'est pas démarré."
    error "✘ [EN] Docker is unavailable or the daemon is not running."
    exit 1
  fi

  start_container
  wait_for_ollama
  select_model
  print_success
}

main "$@"
