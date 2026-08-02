#!/usr/bin/env bash
set -euo pipefail

kit_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
crewai_dir="${1:-}"
service_account="${2:-}"
webhook_url="${3:-}"
google_user_id="${4:-}"

usage() {
  echo "Usage: $0 CREWAI_DIR SERVICE_ACCOUNT_JSON HTTPS_WEBHOOK users/NUMERIC_ID" >&2
}

if [[ -z "$crewai_dir" || -z "$service_account" || -z "$webhook_url" || -z "$google_user_id" ]]; then
  usage
  exit 2
fi
if [[ "$crewai_dir" != /* || "$service_account" != /* ]]; then
  echo "Les chemins doivent être absolus." >&2
  exit 2
fi
if [[ ! -f "$crewai_dir/config/tasks.yaml" || ! -f "$service_account" ]]; then
  echo "tasks.yaml ou le compte de service est introuvable." >&2
  exit 2
fi
if [[ ! "$webhook_url" =~ ^https://[^[:space:]]+/googlechat/?$ ]]; then
  echo "L'URL doit être HTTPS et se terminer par /googlechat." >&2
  exit 2
fi
if [[ ! "$google_user_id" =~ ^users/[0-9]+$ ]]; then
  echo "Utilisez un identifiant Google Chat stable: users/1234567890" >&2
  exit 2
fi
command -v docker >/dev/null || { echo "Docker est requis." >&2; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose v2 est requis." >&2; exit 1; }

install -d -m 0700 "$kit_dir/runtime/openclaw" "$kit_dir/runtime/crewai-admin"
python3 - "$kit_dir/openclaw.container.json5.example" "$kit_dir/runtime/openclaw/openclaw.json.pending" "$webhook_url" "$google_user_id" <<'PY'
import pathlib, sys
source, target, webhook, user = sys.argv[1:]
text = pathlib.Path(source).read_text(encoding="utf-8")
text = text.replace("__GOOGLE_CHAT_WEBHOOK_URL__", webhook)
text = text.replace("__GOOGLE_CHAT_USER_ID__", user)
pathlib.Path(target).write_text(text, encoding="utf-8")
PY
printf '%s\n' '{ gateway: { mode: "local", auth: { mode: "token" }, bind: "loopback", port: 18789 } }' \
  > "$kit_dir/runtime/openclaw/openclaw.json"
chmod 0600 \
  "$kit_dir/runtime/openclaw/openclaw.json" \
  "$kit_dir/runtime/openclaw/openclaw.json.pending"

gateway_token="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
umask 077
{
  printf 'CREWAI_PROJECT_DIR=%s\n' "$crewai_dir"
  printf 'GOOGLE_CHAT_SERVICE_ACCOUNT_FILE=%s\n' "$service_account"
  printf 'OPENCLAW_GATEWAY_TOKEN=%s\n' "$gateway_token"
  printf 'CONTAINER_UID=%s\n' "$(id -u)"
  printf 'CONTAINER_GID=%s\n' "$(id -g)"
  printf 'BIND_ADDRESS=127.0.0.1\n'
  printf 'PUBLIC_PORT=8080\n'
} > "$kit_dir/.env.container"

docker compose --env-file "$kit_dir/.env.container" -f "$kit_dir/compose.secure.yml" build
docker compose --env-file "$kit_dir/.env.container" -f "$kit_dir/compose.secure.yml" run --rm \
  --entrypoint node openclaw-crewai \
  /app/dist/index.js plugins install @openclaw/googlechat
mv "$kit_dir/runtime/openclaw/openclaw.json.pending" \
  "$kit_dir/runtime/openclaw/openclaw.json"
docker compose --env-file "$kit_dir/.env.container" -f "$kit_dir/compose.secure.yml" up -d

for _attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/readyz >/dev/null; then
    echo "Conteneur prêt. Publiez uniquement http://127.0.0.1:8080/googlechat derrière HTTPS."
    exit 0
  fi
  sleep 2
done
echo "Le contrôle de santé a échoué; consultez docker compose logs." >&2
docker compose --env-file "$kit_dir/.env.container" -f "$kit_dir/compose.secure.yml" ps >&2 || true
docker compose --env-file "$kit_dir/.env.container" -f "$kit_dir/compose.secure.yml" logs --tail 200 openclaw-crewai >&2 || true
exit 1
