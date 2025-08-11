#!/bin/bash
# setup_api.sh - Installe un environnement Python pour une API
# et configure Ollama avec le modèle Mistral.
set -euo pipefail

# Variables
APP_PATH="$HOME/mistral_api.py"

# Require root privileges for package installation
if [[ $EUID -ne 0 ]]; then
    echo "❌ Ce script doit être exécuté en tant que root" >&2
    exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo "❌ apt-get n'est pas disponible sur ce système" >&2
    exit 1
fi

echo "🔧 Mise à jour des paquets et installation des dépendances..."
apt-get update
apt-get install -y python3 python3-pip curl

if ! command -v curl >/dev/null 2>&1; then
    echo "❌ curl n'est pas disponible" >&2
    exit 1
fi

python3 -m venv /opt/mistral-env
source /opt/mistral-env/bin/activate

echo "🐍 Installation des bibliothèques Python..."
pip install --upgrade pip
pip install flask requests

echo "⬇️ Installation d'Ollama..."
# Télécharge install.sh séparément, vérifie son empreinte SHA-256 puis l'exécute.
# Le fichier install.sh.sha256 fourni par Ollama contient la somme attendue.
curl -fsSL https://ollama.ai/install.sh -o install.sh
curl -fsSL https://ollama.ai/install.sh.sha256 -o install.sh.sha256
if sha256sum -c install.sh.sha256; then
    bash install.sh
    rm -f install.sh install.sh.sha256
else
    echo "❌ Échec de la vérification de l'intégrité d'install.sh" >&2
    exit 1
fi

echo "📦 Téléchargement du modèle Mistral..."
ollama pull mistral

echo "🛠 Création de l'API Flask dans $APP_PATH..."
cat <<'APP' > "$APP_PATH"
from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json(force=True)
    prompt = data.get('prompt', '')
    if not prompt.strip():
        return jsonify({"error": "Prompt vide"}), 400
    result = subprocess.run(['ollama', 'run', 'mistral', prompt], capture_output=True, text=True)
    if result.returncode != 0:
        return jsonify({"error": result.stderr.strip()}), 500
    return jsonify({"response": result.stdout.strip()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
APP

echo "✅ API créée avec succès : $APP_PATH"
echo "▶️ Avant de la lancer, activez l'environnement : source /opt/mistral-env/bin/activate"
echo "▶️ Lancez-la avec : python $APP_PATH"
