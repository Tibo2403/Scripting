#!/usr/bin/env bash
set -euo pipefail

kit_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m py_compile \
  "$kit_dir/crewai_admin_mcp.py" \
  "$kit_dir/webhook_proxy.py"
bash -n \
  "$kit_dir/setup.sh" \
  "$kit_dir/install-secure-container.sh" \
  "$kit_dir/container-entrypoint.sh" \
  "$kit_dir/deploy/install-vm.sh"

python3 - "$kit_dir/compose.secure.yml" "$kit_dir/Dockerfile" <<'PY'
import pathlib, sys, yaml
compose = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
service = compose["services"]["openclaw-crewai"]
assert service["read_only"] is True
assert "ALL" in service["cap_drop"]
assert "no-new-privileges:true" in service["security_opt"]
assert service["user"] == "1000:1000"
assert service["ports"][0].startswith("${BIND_ADDRESS:-127.0.0.1}:")
dockerfile = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
assert "USER node" in dockerfile
assert "2026.7.1" in dockerfile
print("Contrôles statiques du conteneur: OK")
PY

if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  docker build -t openclaw-crewai-admin:test "$kit_dir"
else
  echo "Docker absent: construction de l'image non exécutée." >&2
  exit 3
fi

