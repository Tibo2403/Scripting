#!/usr/bin/env bash
set -euo pipefail

kit_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m py_compile \
  "$kit_dir/crewai_admin_mcp.py" \
  "$kit_dir/webhook_proxy.py"
bash -n \
  "$kit_dir/setup.sh" \
  bash "$kit_dir/install-secure-container.sh" \
  "$kit_dir/container-entrypoint.sh" \
  "$kit_dir/deploy/install-vm.sh"

python3 - "$kit_dir/compose.secure.yml" "$kit_dir/Dockerfile" <<'PY'
import pathlib, sys, yaml
compose = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
service = compose["services"]["openclaw-crewai"]
assert service["read_only"] is True
assert "ALL" in service["cap_drop"]
assert "no-new-privileges:true" in service["security_opt"]
assert service["user"] == "${CONTAINER_UID:-1000}:${CONTAINER_GID:-1000}"
assert "OPENCLAW_GATEWAY_TOKEN" in service["environment"]
assert service["ports"][0].startswith("${BIND_ADDRESS:-127.0.0.1}:")
dockerfile = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
assert "USER node" in dockerfile
assert "2026.7.1" in dockerfile
print("Contrôles statiques du conteneur: OK")
PY

if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  test_root="$(mktemp -d)"
  cleanup() {
    docker compose --env-file "$kit_dir/.env.container" -f "$kit_dir/compose.secure.yml" down -v >/dev/null 2>&1 || true
    rm -rf "$test_root"
  }
  trap cleanup EXIT
  install -d "$test_root/crewai/config"
  cp "$kit_dir/sample-crewai/config/tasks.yaml" "$test_root/crewai/config/tasks.yaml"
  printf '{"type":"service_account","project_id":"ci-test"}\n' > "$test_root/googlechat.json"
  "$kit_dir/install-secure-container.sh" \
    "$test_root/crewai" \
    "$test_root/googlechat.json" \
    "https://ci.invalid/googlechat" \
    "users/1234567890"
  curl -fsS http://127.0.0.1:8080/healthz >/dev/null
  curl -fsS http://127.0.0.1:8080/readyz >/dev/null
  test "$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/)" = "404"
  docker compose --env-file "$kit_dir/.env.container" -f "$kit_dir/compose.secure.yml" exec -T \
    openclaw-crewai python3 -c \
    'import sys; sys.path.insert(0,"/opt/crewai-admin"); import crewai_admin_mcp as c; assert c.list_tasks()["tasks"]'
else
  echo "Docker absent: construction de l'image non exécutée." >&2
  exit 3
fi
