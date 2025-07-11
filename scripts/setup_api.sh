#!/bin/bash
# setup_api.sh - Installe un environnement Python pour une API
# et configure Ollama avec le modèle Mistral.
set -euo pipefail

# Variables
APP_PATH="$HOME/mistral_api.py"

echo "🔧 Mise à jour des paquets et installation des dépendances..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip curl

echo "🐍 Installation des bibliothèques Python..."
pip3 install --upgrade pip
pip3 install flask requests

echo "⬇️ Installation d'Ollama..."
# WARNING: executing a remote script with curl | bash can be dangerous.
# Review https://ollama.ai/install.sh or verify its checksum before running.
# Example:
#   curl -fsSL https://ollama.ai/install.sh -o install.sh
#   sha256sum install.sh # compare with the expected value
#   bash install.sh
curl -fsSL https://ollama.ai/install.sh | bash

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
echo "▶️ Lancez-la avec : python3 $APP_PATH"
