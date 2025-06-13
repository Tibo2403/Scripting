#!/bin/bash
# setup_api.sh - Installe un environnement Python pour une API
# et configure Ollama avec le modèle Mistral.
set -e

# Mise à jour des paquets et installation des dépendances de base
sudo apt-get update
sudo apt-get install -y python3 python3-pip curl

# Installation des dépendances Python
pip3 install flask requests

# Installation d'Ollama (inclut les dépendances du modèle)
curl -fsSL https://ollama.ai/install.sh | bash

# Téléchargement du modèle Mistral
ollama pull mistral

# Création d'un petit exemple d'API utilisant Flask
cat <<'APP' > ~/mistral_api.py
from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json(force=True)
    prompt = data.get('prompt', '')
    result = subprocess.run(['ollama', 'run', 'mistral', prompt], capture_output=True, text=True)
    return jsonify({"response": result.stdout.strip()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
APP

echo "API exemple creee dans ~/mistral_api.py"
echo "Lancez-la avec : python3 ~/mistral_api.py"
