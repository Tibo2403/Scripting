#!/bin/bash
# setup_api.sh - Installe un environnement Python pour une API
# et configure Ollama avec le modèle Mistral.
# Option --offline pour ignorer les opérations réseau.
set -euo pipefail

# Variables
APP_PATH="$HOME/mistral_api.py"
OFFLINE=false

for arg in "$@"; do
    case "$arg" in
        --offline) OFFLINE=true ;;
    esac
done

# Require root privileges for package installation
if [[ $EUID -ne 0 ]]; then
    echo "❌ Ce script doit être exécuté en tant que root" >&2
    exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo "❌ apt-get n'est pas disponible sur ce système" >&2
    exit 1
fi

# Vérifie la connectivité réseau avant d'installer quoi que ce soit
if [[ "$OFFLINE" = false ]]; then
    echo "🌐 Vérification de la connectivité réseau..."
    if ! ping -c1 -W3 8.8.8.8 >/dev/null 2>&1; then
        echo "❌ Aucune connectivité réseau. Vérifiez votre connexion." >&2
        exit 1
    fi
    if ! command -v curl >/dev/null 2>&1; then
        echo "❌ curl est requis pour le test HTTP" >&2
        exit 1
    fi
    if ! curl --fail --silent https://example.com >/dev/null; then
        echo "❌ Le test HTTP a échoué" >&2
        exit 1
    fi

    echo "🔧 Mise à jour des paquets et installation des dépendances..."
    if ! apt-get update; then
        echo "❌ Échec de 'apt-get update'" >&2
        exit 1
    fi
    if ! apt-get install -y python3 python3-pip curl; then
        echo "❌ Échec de 'apt-get install'" >&2
        exit 1
    fi
    if ! command -v curl >/dev/null 2>&1; then
        echo "❌ curl n'est pas disponible" >&2
        exit 1
    fi
else
    echo "⚠️ Mode hors ligne : vérifications réseau et installation ignorées"
fi

python3 -m venv /opt/mistral-env
source /opt/mistral-env/bin/activate

if [[ "$OFFLINE" = false ]]; then
    echo "🐍 Installation des bibliothèques Python..."
    pip install --upgrade pip
    pip install flask==2.3.2 requests==2.31.0

    echo "⬇️ Installation d'Ollama..."
    # Télécharge install.sh séparément, vérifie son empreinte SHA-256 puis l'exécute.
    # Le fichier install.sh.sha256 fourni par Ollama contient la somme attendue.
    curl -fsSL https://ollama.ai/install.sh -o install.sh
    curl -fsSL https://ollama.ai/install.sh.sha256 -o install.sh.sha256
    # Vérifie la disponibilité de sha256sum avant la vérification d'intégrité
    if ! command -v sha256sum >/dev/null 2>&1; then
        echo "❌ sha256sum n'est pas disponible" >&2
        exit 1
    fi
    if sha256sum -c install.sh.sha256; then
        bash install.sh
        rm -f install.sh install.sh.sha256
    else
        echo "❌ Échec de la vérification de l'intégrité d'install.sh" >&2
        exit 1
    fi

    echo "📦 Téléchargement du modèle Mistral..."
    ollama pull mistral
else
    echo "⚠️ Mode hors ligne : dépendances Python et téléchargements ignorés"
fi

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
