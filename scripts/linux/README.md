# Linux Scripts

This directory contains Bash scripts for Linux administration, dependency checks, and authorized security testing.

## Scripts

- `check_dependencies.sh` - checks required command line tools and can optionally install missing packages with `--install`.
- `dependencies.conf` - configurable list of CLI dependencies and PowerShell modules used by `check_dependencies.sh`.
- `setup_api.sh` - installs and configures a local Mistral API environment.
- `pentest_discovery.sh` - discovery phase for authorized security assessments.
- `pentest_verification.sh` - verification phase, with optional public CVE enrichment.
- `pentest_exploitation.sh` - prioritized SearchSploit review for explicitly authorized tests.
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

## Public vulnerability data

The verification phase can enrich CVE identifiers found in both Nmap and OpenVAS XML. It queries the CISA Known Exploited Vulnerabilities catalog, NVD CVE API 2.0, and FIRST EPSS, then writes `<host>_cve_enrichment.tsv` and `.json` beside the scanner results. Only CVE identifiers are sent to NVD and FIRST; target addresses and scanner details remain local.

```bash
bash pentest_verification.sh \
  --results ../../pentest_results/example \
  --skip-metasploit \
  --enrich-open-data \
  --yes-i-am-authorized
```

Set `NVD_API_KEY` to use an NVD API key without placing it in arguments or logs. Responses are cached for 24 hours in `<results>/.open_data_cache`; use `--offline-enrichment` to prohibit network access and read only that cache. A source outage is non-fatal: the CVE list and any available source data are still written.

Priorities are a review heuristic, not proof that a host is vulnerable or exploitable: CISA KEV entries are `critical`; EPSS >= 0.10 or CVSS >= 9.0 is `high`; EPSS >= 0.01 or CVSS >= 7.0 is `medium`; all others remain `review`. The exploitation helper consumes the TSV in that order but only generates SearchSploit suggestions.

This product uses data from the NVD API but is not endorsed or certified by the NVD.

Attempt dependency installation:

```bash
bash check_dependencies.sh --install
```
