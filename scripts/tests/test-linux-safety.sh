#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

assert_ok() {
    local description="$1"
    shift
    echo "[test] $description"
    "$@"
}

assert_no_artifacts() {
    if [[ -d pentest_results || -d wifi_captures ]]; then
        echo "Dry-run created runtime artifacts." >&2
        exit 1
    fi
}

SENSITIVE_SCRIPTS=(
    scripts/linux/pentest_discovery.sh
    scripts/linux/pentest_verification.sh
    scripts/linux/pentest_exploitation.sh
    scripts/linux/scan_wifi.sh
    scripts/linux/stealth_post.sh
)

for script in "${SENSITIVE_SCRIPTS[@]}"; do
    assert_ok "$script --help" bash "$script" --help >/dev/null 2>&1
done

assert_ok "discovery dry-run" \
    bash scripts/linux/pentest_discovery.sh --dry-run --yes-i-am-authorized >/dev/null 2>&1

assert_ok "verification dry-run" \
    bash scripts/linux/pentest_verification.sh --dry-run --yes-i-am-authorized >/dev/null 2>&1

assert_ok "exploitation dry-run" \
    bash scripts/linux/pentest_exploitation.sh --dry-run --yes-i-am-authorized >/dev/null 2>&1

assert_ok "wifi dry-run" \
    bash scripts/linux/scan_wifi.sh --dry-run --yes-i-am-authorized --non-interactive \
        --bssid 00:11:22:33:44:55 --essid LabNetwork >/dev/null 2>&1

assert_ok "encrypted transfer dry-run" \
    env FTP_USER=user FTP_PASS=pass FTP_HOST=example.com FTP_PATH=uploads/test.gpg GPG_PASSPHRASE=secret \
        bash scripts/linux/stealth_post.sh --dry-run --yes-i-am-authorized >/dev/null 2>&1

assert_no_artifacts
echo "Linux safety tests passed."
