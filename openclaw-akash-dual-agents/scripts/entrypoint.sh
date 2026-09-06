#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
template="${OPENCLAW_TEMPLATE_DIR:-/opt/openclaw-template}"
runtime="${OPENCLAW_RUNTIME_DIR:-/opt/openclaw-runtime}"
data="${OPENCLAW_DATA_DIR:-/data}"
export OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-${data}/openclaw}"
export OPENCLAW_CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-${OPENCLAW_STATE_DIR}/openclaw.json}"
node "${runtime}/config.mjs" dual "${OPENCLAW_CONFIG_PATH}"
openclaw config validate
bash "${template}/scripts/validate-models.sh"
mkdir -p "${data}/repos"
for agent in agent-qwen agent-deepseek; do
  workspace="${data}/workspaces/${agent}"
  mkdir -p "${workspace}"
  for file in SOUL.md TOOLS.md HEARTBEAT.md; do
    if [[ ! -e "${workspace}/${file}" ]]; then
      cp "${template}/agents/${agent}/${file}" "${workspace}/${file}"
    fi
  done
  if [[ ! -e "${workspace}/AGENTS.md" ]]; then
    printf '# AGENTS\n\nRead SOUL.md and TOOLS.md. Review repositories in REPOSITORIES under /data/repos/OWNER/NAME.\n' > "${workspace}/AGENTS.md"
  fi
done
export GH_TOKEN="${GITHUB_TOKEN}"
IFS=',' read -ra repos <<< "${REPOSITORIES}"
for repo in "${repos[@]}"; do
  repo="${repo//[[:space:]]/}"
  dest="${data}/repos/${repo}"
  mkdir -p "${dest%/*}"
  if [[ -d "${dest}/.git" ]]; then
    origin="$(git -C "${dest}" remote get-url origin)"
    if [[ "$origin" != "https://github.com/${repo}.git" && "$origin" != "https://github.com/${repo}" ]]; then
      echo 'Existing repository origin does not match REPOSITORIES.' >&2
      exit 1
    fi
    # Preserve local work: never reset, merge or pull automatically.
    git -C "${dest}" -c credential.helper= -c 'credential.helper=!gh auth git-credential' fetch --prune origin
  elif [[ -e "${dest}" ]]; then
    echo 'Checkout destination exists but is not a Git repository.' >&2
    exit 1
  else
    gh repo clone "${repo}" "${dest}" -- --filter=blob:none
  fi
done
exec openclaw gateway --port "${OPENCLAW_PORT:-18789}"
