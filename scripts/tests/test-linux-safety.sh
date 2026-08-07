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

assert_contains() {
    local file="$1"
    local expected="$2"
    if ! grep -Fq "$expected" "$file"; then
        echo "Expected '$expected' in $file" >&2
        exit 1
    fi
}

assert_exploitation_enrichment_context() {
    local temp_root results_dir fake_bin search_file calls_file
    temp_root="$(mktemp -d)"
    results_dir="$temp_root/results"
    fake_bin="$temp_root/bin"
    search_file="$temp_root/suggestions.txt"
    calls_file="$temp_root/searchsploit.calls"
    mkdir -p "$results_dir" "$fake_bin"
    trap '[[ "${temp_root:-}" == /tmp/* ]] && rm -rf "$temp_root"' RETURN

    touch "$results_dir/10.0.0.5_vuln.xml"
    cat >"$results_dir/10.0.0.5_cve_enrichment.tsv" <<'EOF'
cve	priority	kev	kev_due_date	known_ransomware	epss	epss_percentile	cvss	severity	published	description
CVE-2024-1111	critical	True	2026-08-15	Known	0.42	0.95	8.8	HIGH	2024-01-01	Example issue
CVE-2024-2222	medium	False			0.02	0.50	7.1	HIGH	2024-02-01	Second issue
EOF
    cat >"$fake_bin/searchsploit" <<EOF
#!/bin/bash
echo "\$1" >>"$calls_file"
echo "fake exploit for \$1"
EOF
    chmod +x "$fake_bin/searchsploit"

    PATH="$fake_bin:$PATH" bash scripts/linux/pentest_exploitation.sh \
        --results "$results_dir" \
        --search-file "$search_file" \
        --yes-i-am-authorized >/dev/null

    assert_contains "$calls_file" "CVE-2024-1111"
    assert_contains "$calls_file" "CVE-2024-2222"
    assert_contains "$search_file" "priority=critical, KEV=True, EPSS=0.42, CVSS=8.8/HIGH"
    assert_contains "$search_file" "priority=medium, KEV=False, EPSS=0.02, CVSS=7.1/HIGH"
}

SENSITIVE_SCRIPTS=(
    scripts/pentest_discovery.sh
    scripts/pentest_verification.sh
    scripts/pentest_exploitation.sh
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

assert_ok "verification open-data dry-run" \
    bash scripts/linux/pentest_verification.sh --dry-run --enrich-open-data \
        --yes-i-am-authorized >/dev/null 2>&1

assert_ok "exploitation dry-run" \
    bash scripts/linux/pentest_exploitation.sh --dry-run --yes-i-am-authorized >/dev/null 2>&1

assert_ok "discovery wrapper dry-run" \
    bash scripts/pentest_discovery.sh --dry-run --yes-i-am-authorized >/dev/null 2>&1

assert_ok "verification wrapper dry-run" \
    bash scripts/pentest_verification.sh --dry-run --yes-i-am-authorized >/dev/null 2>&1

assert_ok "exploitation wrapper dry-run" \
    bash scripts/pentest_exploitation.sh --dry-run --yes-i-am-authorized >/dev/null 2>&1

assert_ok "exploitation enrichment context" assert_exploitation_enrichment_context

assert_ok "wifi dry-run" \
    bash scripts/linux/scan_wifi.sh --dry-run --yes-i-am-authorized --non-interactive \
        --bssid 00:11:22:33:44:55 --essid LabNetwork >/dev/null 2>&1

assert_ok "encrypted transfer dry-run" \
    env FTP_USER=user FTP_PASS=pass FTP_HOST=example.com FTP_PATH=uploads/test.gpg GPG_PASSPHRASE=secret \
        bash scripts/linux/stealth_post.sh --dry-run --yes-i-am-authorized >/dev/null 2>&1

assert_no_artifacts
echo "Linux safety tests passed."
