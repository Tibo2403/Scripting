#!/bin/bash
# check_dependencies.sh - Vérifie la présence des outils requis pour les scripts du dépôt
# ⚠️  Utiliser avant d'exécuter les scripts pour s'assurer que toutes les dépendances sont installées
set -euo pipefail

# Outils en ligne de commande requis
CLI_DEPS=(nmap gvm-cli pwsh)

# Modules PowerShell à vérifier
PS_MODULES=("Hyper-V" "ExchangeOnlineManagement" "MicrosoftTeams" "PnP.PowerShell")

missing=0

for cmd in "${CLI_DEPS[@]}"; do
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "✅ $cmd disponible"
    else
        echo "❌ $cmd introuvable" >&2
        missing=1
    fi
done

if command -v pwsh >/dev/null 2>&1; then
    for mod in "${PS_MODULES[@]}"; do
        if pwsh -NoProfile -Command "Get-Module -ListAvailable -Name '$mod' | Out-Null" 2>/dev/null; then
            echo "✅ Module PowerShell $mod disponible"
        else
            echo "❌ Module PowerShell $mod manquant" >&2
            missing=1
        fi
    done
else
    echo "❌ pwsh introuvable - impossible de vérifier les modules PowerShell" >&2
fi

if [[ $missing -eq 0 ]]; then
    echo "Toutes les dépendances sont satisfaites."
else
    echo "Certaines dépendances sont manquantes. Veuillez les installer." >&2
fi
