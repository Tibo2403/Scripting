#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

required=(DEEPINFRA_API_KEY GITHUB_TOKEN TOKEN_BOT_A TOKEN_BOT_B OPENCLAW_GATEWAY_TOKEN QWEN_MODEL_ID DEEPSEEK_MODEL_ID)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
done

mkdir -p /data/openclaw /data/workspaces/agent-qwen /data/workspaces/agent-deepseek /data/repos
if [[ ! -f /data/openclaw/openclaw.json ]]; then
  cp /opt/openclaw-template/openclaw.json /data/openclaw/openclaw.json
fi
for agent in agent-qwen agent-deepseek; do
  cp -n /opt/openclaw-template/agents/${agent}/SOUL.md /data/workspaces/${agent}/SOUL.md
  cp -n /opt/openclaw-template/agents/${agent}/TOOLS.md /data/workspaces/${agent}/TOOLS.md
  cp -n /opt/openclaw-template/agents/${agent}/HEARTBEAT.md /data/workspaces/${agent}/HEARTBEAT.md
  printf '# AGENTS\n\nFollow SOUL.md, TOOLS.md and HEARTBEAT.md. Work only in repositories explicitly listed in REPOSITORIES.\n' > /data/workspaces/${agent}/AGENTS.md

done

export GH_TOKEN="${GITHUB_TOKEN}"
IFS=',' read -ra repos <<< "${REPOSITORIES:-Tibo2403/Scripting}"
for repo in "${repos[@]}"; do
  repo="${repo//[[:space:]]/}"
  [[ -z "${repo}" ]] && continue
  dest="/data/repos/${repo##*/}"
  if [[ -d "${dest}/.git" ]]; then
    git -C "${dest}" fetch --prune origin || true
  else
    gh repo clone "${repo}" "${dest}" -- --filter=blob:none
  fi
done

/opt/openclaw-template/scripts/validate-models.sh
openclaw doctor || true
exec openclaw gateway --port 18789
