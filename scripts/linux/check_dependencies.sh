#!/bin/bash
# check_dependencies.sh - Vérifie la présence des outils requis pour les scripts du dépôt
# Options :
#   --help        Affiche l'usage et les dépendances
#   --install     Installe les dépendances manquantes
#   --dry-run     Simule l'installation sans effectuer de modifications
#   --prefix DIR  Installe les paquets dans DIR sans droits root
set -euo pipefail

# Outils en ligne de commande requis
CLI_DEPS=(nmap gvm-cli pwsh)
# Modules PowerShell à vérifier
PS_MODULES=("Hyper-V" "ExchangeOnlineManagement" "MicrosoftTeams" "PnP.PowerShell")

INSTALL=false
DRY_RUN=false
PREFIX=""

usage() {
    cat <<EOF
Usage: $0 [--help] [--install] [--dry-run] [--prefix DIR]
Vérifie la présence des dépendances nécessaires aux scripts.

Options:
  --help        Affiche cette aide et la liste des dépendances
  --install     Installe les dépendances manquantes
  --dry-run     Simule l'installation (aucune modification)
  --prefix DIR  Installe les paquets dans DIR sans droits root

Dépendances CLI : ${CLI_DEPS[*]}
Modules PowerShell : ${PS_MODULES[*]}
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --install) INSTALL=true ;;
        --dry-run) DRY_RUN=true ;;
        --prefix)
            if [[ -n "${2:-}" ]]; then
                PREFIX="$2"
                shift
            else
                echo "--prefix nécessite un argument" >&2
                exit 1
            fi
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "Option inconnue : $1" >&2
            usage
            exit 1
            ;;
    esac
    shift
done

APT_UPDATED=false
apt_update() {
    if ! $APT_UPDATED; then
        if $DRY_RUN; then
            echo "(dry-run) apt-get update -qq"
        else
            if command -v apt-get >/dev/null 2>&1; then
                if [[ $EUID -ne 0 ]]; then
                    sudo apt-get update -qq
                else
                    apt-get update -qq
                fi
            fi
        fi
        APT_UPDATED=true
    fi
}

# Installe un paquet en utilisant le gestionnaire de paquets disponible
install_package() {
    local pkg="$1"
    if $DRY_RUN; then
        apt_update
        echo "(dry-run) installation de $pkg"
        return 0
    fi

    if command -v apt-get >/dev/null 2>&1; then
        if [[ -n "$PREFIX" ]]; then
            apt_update
            tmpdir=$(mktemp -d)
            if (cd "$tmpdir" && apt-get download "$pkg" >/dev/null 2>&1); then
                deb=$(find "$tmpdir" -name "*.deb" | head -n1)
                if [[ -n "$deb" ]]; then
                    mkdir -p "$PREFIX"
                    dpkg -x "$deb" "$PREFIX" >/dev/null 2>&1 && \
                        echo "✅ $pkg installé dans $PREFIX" || \
                        echo "❌ Échec de l'installation de $pkg" >&2
                else
                    echo "❌ Téléchargement de $pkg échoué" >&2
                    return 1
                fi
            else
                echo "❌ Impossible de télécharger $pkg" >&2
                return 1
            fi
            rm -rf "$tmpdir"
        else
            apt_update
            if [[ $EUID -ne 0 ]]; then
                sudo apt-get install -y "$pkg"
            else
                apt-get install -y "$pkg"
            fi
        fi
    elif command -v yum >/dev/null 2>&1; then
        echo "Tentative d'installation de $pkg via yum..."
        if [[ $EUID -ne 0 ]]; then
            sudo yum install -y "$pkg"
        else
            yum install -y "$pkg"
        fi
    elif command -v dnf >/dev/null 2>&1; then
        echo "Tentative d'installation de $pkg via dnf..."
        if [[ $EUID -ne 0 ]]; then
            sudo dnf install -y "$pkg"
        else
            dnf install -y "$pkg"
        fi
    elif command -v pacman >/dev/null 2>&1; then
        echo "Tentative d'installation de $pkg via pacman..."
        if [[ $EUID -ne 0 ]]; then
            sudo pacman -Sy --noconfirm "$pkg"
        else
            pacman -Sy --noconfirm "$pkg"
        fi
    else
        echo "Veuillez installer $pkg manuellement." >&2
        return 1
    fi
}

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
                if $DRY_RUN; then
                    echo "(dry-run) installation du module $mod"
                else
                    echo "Tentative d'installation du module $mod..."
                    pwsh -NoProfile -Command "Install-Module -Name '$mod' -Scope CurrentUser -Force" || \
                        echo "Échec de l'installation de $mod" >&2
                fi
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

if [[ -n "$PREFIX" ]]; then
    echo "ℹ️  Pensez à ajouter $PREFIX/usr/bin à votre PATH pour utiliser les outils installés."
fi

