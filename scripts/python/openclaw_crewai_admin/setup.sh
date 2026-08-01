#!/usr/bin/env bash
set -euo pipefail

kit_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="${1:-}"

if [[ -z "$project_dir" ]]; then
  echo "Usage: $0 /chemin/absolu/vers/projet-crewai" >&2
  exit 2
fi

if [[ "$project_dir" != /* ]]; then
  echo "Le chemin du projet CrewAI doit être absolu." >&2
  exit 2
fi

if [[ ! -f "$project_dir/config/tasks.yaml" ]]; then
  echo "Fichier introuvable: $project_dir/config/tasks.yaml" >&2
  exit 2
fi

python3 -m venv "$kit_dir/.venv"
"$kit_dir/.venv/bin/python" -m pip install --upgrade pip
"$kit_dir/.venv/bin/python" -m pip install -r "$kit_dir/requirements.txt"

sed "s|^CREWAI_PROJECT_DIR=.*|CREWAI_PROJECT_DIR=$project_dir|" \
  "$kit_dir/.env.example" > "$kit_dir/.env"

sed \
  -e "s|__PYTHON__|$kit_dir/.venv/bin/python|g" \
  -e "s|__SERVER__|$kit_dir/crewai_admin_mcp.py|g" \
  "$kit_dir/openclaw-mcp.json5.example" > "$kit_dir/openclaw-mcp.json5"

echo "Installation terminée."
echo "Configuration MCP générée: $kit_dir/openclaw-mcp.json5"
echo "Test: $kit_dir/.venv/bin/python $kit_dir/crewai_admin_mcp.py"

