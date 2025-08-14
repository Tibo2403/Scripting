#!/bin/bash
# check_dependencies.sh - Vérifie la présence des outils requis pour les scripts du dépôt
# Utilisation : check_dependencies.sh [--install] [--help]
# Sans option, le script signale les dépendances manquantes sans les installer.
#   --install : installe automatiquement les dépendances manquantes.
#   --help    : affiche ce message et quitte.
set -euo pipefail

INSTALL=false
APT_UPDATED=false

show_help() {
    cat <<'EOF'
Usage: check_dependencies.sh [--install] [--help]
Vérifie la présence des dépendances requises pour les scripts du dépôt.
Sans option, le script se contente de signaler les dépendances manquantes.
  --install : installe automatiquement les dépendances manquantes.
  --help    : affiche cette aide et quitte.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --install) INSTALL=true ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "Option inconnue: $arg" >&2
            exit 1
            ;;
    esac
done

# Installe un paquet en utilisant le gestionnaire de paquets disponible
install_package() {
    local pkg="$1"
    if command -v apt-get >/dev/null 2>&1; then
        echo "Tentative d'installation de $pkg via apt-get..."
        if ! $APT_UPDATED; then
            sudo apt-get update -qq
            APT_UPDATED=true
        fi
        sudo apt-get install -y "$pkg"
    elif command -v yum >/dev/null 2>&1; then
        echo "Tentative d'installation de $pkg via yum..."
        sudo yum install -y "$pkg"
    elif command -v dnf >/dev/null 2>&1; then
        echo "Tentative d'installation de $pkg via dnf..."
        sudo dnf install -y "$pkg"
    elif command -v pacman >/dev/null 2>&1; then
        echo "Tentative d'installation de $pkg via pacman..."
        sudo pacman -Sy --noconfirm "$pkg"
    else
        echo "Veuillez installer $pkg manuellement." >&2
        return 1
    fi
}

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
        if $INSTALL; then
            install_package "$cmd" || echo "Échec de l'installation de $cmd" >&2
        else
            echo "→ Installez $cmd avec votre gestionnaire de paquets (apt-get, yum, dnf ou pacman)"
        fi
    fi
done

if command -v pwsh >/dev/null 2>&1; then
    for mod in "${PS_MODULES[@]}"; do
        if pwsh -NoProfile -Command "Get-Module -ListAvailable -Name '$mod' | Out-Null" 2>/dev/null; then
            echo "✅ Module PowerShell $mod disponible"
        else
            echo "❌ Module PowerShell $mod manquant" >&2
            missing=1
            if $INSTALL; then
                echo "Tentative d'installation du module $mod..."
                pwsh -NoProfile -Command "Install-Module -Name '$mod' -Scope CurrentUser -Force" || echo "Échec de l'installation de $mod" >&2
            else
                echo "→ Installez avec : pwsh -NoProfile -Command \"Install-Module -Name '$mod'\""
            fi
        fi
    done
else
    echo "❌ pwsh introuvable - impossible de vérifier les modules PowerShell" >&2
    if $INSTALL; then
        install_package "powershell" || echo "Échec de l'installation de powershell" >&2
    fi
fi

if [[ $missing -eq 0 ]]; then
    echo "Toutes les dépendances sont satisfaites."
else
    echo "Certaines dépendances sont manquantes. Veuillez les installer." >&2
fi
