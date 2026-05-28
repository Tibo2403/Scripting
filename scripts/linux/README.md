# Linux Scripts

This directory contains Bash scripts for Linux administration, dependency checks, and authorized security testing.

## Scripts

- `check_dependencies.sh` - checks required command line tools and can optionally install missing packages with `--install`.
- `dependencies.conf` - configurable list of CLI dependencies and PowerShell modules used by `check_dependencies.sh`.
- `setup_api.sh` - installs and configures a local Mistral API environment.
- `pentest_discovery.sh` - discovery phase for authorized security assessments.
- `pentest_verification.sh` - verification phase for discovered findings.
- `pentest_exploitation.sh` - exploitation phase for explicitly authorized tests.
- `scan_wifi.sh` - Wi-Fi scan helper with logging in `wifi_captures/scan_wifi.log`.
- `stealth_post.sh` - encrypted FTPS transfer helper for authorized post-assessment collection.

## Safety Rules

- Run pentest scripts only against assets listed in an approved scope.
- Keep `targets.txt` limited to systems you own or are authorized to test.
- Do not commit credentials, passphrases, scan output, packet captures, or customer data.
- Prefer lab targets when demonstrating the repository publicly.
- Use `--dry-run` before running discovery, verification, exploitation, Wi-Fi capture, or encrypted transfer helpers.
- Use `--yes-i-am-authorized` only after confirming the target and activity are explicitly approved.

## Validation

```bash
find . -name "*.sh" -print0 | xargs -0 -n1 bash -n
```

Check dependencies:

```bash
bash check_dependencies.sh
```

Review a sensitive script without performing the action:

```bash
bash pentest_discovery.sh --dry-run --yes-i-am-authorized
bash scan_wifi.sh --dry-run --yes-i-am-authorized --non-interactive --bssid 00:11:22:33:44:55 --essid LabNetwork
```

Attempt dependency installation:

```bash
bash check_dependencies.sh --install
```
