# Scripting Toolkit

[![Script Validation](https://github.com/Tibo2403/Scripting/actions/workflows/script-validation.yml/badge.svg)](https://github.com/Tibo2403/Scripting/actions/workflows/script-validation.yml)

Collection of PowerShell, Bash, and Python scripts for system administration, security checks, Microsoft 365 operations, Linux dependency checks, MCP integrations, and authorized lab or pentest workflows.

## Legal Notice

Use the pentest scripts only on systems where you have explicit written authorization. Unauthorized scanning, exploitation, credential access, or data transfer can be illegal and harmful.

The scripts in `scripts/linux/pentest_*.sh`, `scan_wifi.sh`, and `stealth_post.sh` are intended for controlled labs, training environments, or sanctioned security assessments.

## Repository Structure

```text
scripts/
|-- linux/
|   |-- check_dependencies.sh
|   |-- dependencies.conf
|   |-- pentest_discovery.sh
|   |-- pentest_verification.sh
|   |-- pentest_exploitation.sh
|   |-- scan_wifi.sh
|   |-- setup_api.sh
|   `-- stealth_post.sh
|-- powershell/
    |-- DiskUsageReport.ps1
    |-- ExchangeOnlineManagement.ps1
    |-- Get-SystemInfo.ps1
    |-- LinkCrawler.ps1
    |-- ManageServices.ps1
    |-- SecurityCheck.ps1
    |-- SharePointManagement.ps1
    |-- TeamsManagement.ps1
    |-- Test-ScriptSyntax.ps1
    |-- UserManagement.ps1
    `-- VMManagement.ps1
`-- python/
    |-- codex-cost-routing.cmd
    |-- codex_cost_router.py
    |-- litellm-cost-routing.yaml
    |-- Manage-CodexCostRouting.ps1
    |-- mcp_server.py
    |-- README.md
    |-- README_Codex_Cost_Routing.md
    `-- requirements.txt
```

`targets.txt` contains example targets used by the pentest scripts. Keep it limited to systems that you are allowed to test.

See `docs/compatibility-matrix.md` for OS support, privilege requirements, dependencies, risk level, and dry-run availability per script.

Portfolio and maintenance docs:

- `docs/portfolio.md` explains the repository in recruiter/client terms.
- `docs/demo-media.md` lists screenshots and GIFs to capture.
- `docs/issue-backlog.md` contains ready-to-create GitHub issues.
- `CHANGELOG.md` tracks release notes.

## Prerequisites

- PowerShell 5.1+ or PowerShell 7+ for Windows scripts.
- Linux shell tools for Bash scripts.
- Python 3.10+ and the optional `mcp[cli]` package for the MCP server.
- Optional tools depending on the script: `nmap`, `gvm-cli`, `curl`, `gpg`, `pwsh`.
- Optional PowerShell modules: Hyper-V, ExchangeOnlineManagement, MicrosoftTeams, PnP.PowerShell.
- Administrator or root privileges for scripts that manage services, users, VMs, network scans, or security settings.

## Quick Checks

Validate PowerShell syntax:

```powershell
.\scripts\powershell\Test-ScriptSyntax.ps1 -Path .\scripts\powershell
```

Run PowerShell static analysis:

```powershell
Install-Module -Name PSScriptAnalyzer -Scope CurrentUser
Invoke-ScriptAnalyzer -Path .\scripts\powershell -Recurse -Settings .\PSScriptAnalyzerSettings.psd1
```

Validate Bash syntax from Linux, WSL, Git Bash, or CI:

```bash
find scripts/linux -name "*.sh" -print0 | xargs -0 -n1 bash -n
```

Run Bash static analysis:

```bash
find scripts/linux -name "*.sh" -print0 | xargs -0 shellcheck --severity=error
```

Check Linux dependencies:

```bash
bash scripts/linux/check_dependencies.sh
```

Run the Linux safety smoke tests:

```bash
bash scripts/tests/test-linux-safety.sh
```

## PowerShell Examples

```powershell
.\scripts\powershell\Get-SystemInfo.ps1
.\scripts\powershell\ManageServices.ps1 -Action status -ServiceName spooler
.\scripts\powershell\VMManagement.ps1 -Action list
.\scripts\powershell\TeamsManagement.ps1 -Action list
.\scripts\powershell\ExchangeOnlineManagement.ps1 -Action list
.\scripts\powershell\SecurityCheck.ps1
```

`ManageServices.ps1` and `UserManagement.ps1` require an elevated PowerShell session for privileged actions.

## Linux Examples

```bash
bash scripts/linux/check_dependencies.sh
bash scripts/linux/pentest_discovery.sh --dry-run --yes-i-am-authorized
bash scripts/linux/pentest_verification.sh --dry-run --yes-i-am-authorized
bash scripts/linux/pentest_exploitation.sh --dry-run --yes-i-am-authorized
```

For `stealth_post.sh`, pass credentials through environment variables or a local config file that is never committed:

```bash
export FTP_USER="user"
export FTP_PASS="password"
export FTP_HOST="example.com"
export FTP_PATH="uploads/sysinfo.txt.gpg"
export GPG_PASSPHRASE="secret_passphrase"
bash scripts/linux/stealth_post.sh --dry-run --yes-i-am-authorized
```

Sensitive Linux scripts require either an interactive `AUTHORIZED` confirmation or the explicit `--yes-i-am-authorized` flag. Use `--dry-run` first to review planned scans, captures, or transfers.

Use the safe placeholders in `examples/` for lab demos and documentation. Do not commit real targets, credentials, tenant identifiers, scan output, packet captures, or customer data.

## MCP Server

The read-only Python MCP server exposes tools to list, search, inspect, and
validate scripts without executing them. It can also browse documentation and
return a repository summary:

```powershell
pip install -r .\scripts\python\requirements.txt
python .\scripts\python\mcp_server.py
```

Connect an MCP client to `http://localhost:8000/mcp`. See
[`scripts/python/README.md`](scripts/python/README.md) for setup and inspector
instructions.

The optional Codex cost router in `scripts/python/codex_cost_router.py` can
compress one-shot prompts and route them through a self-hosted LiteLLM OSS proxy.
See [`scripts/python/README_Codex_Cost_Routing.md`](scripts/python/README_Codex_Cost_Routing.md).

## CI

The `script-validation.yml` workflow checks:

- PowerShell syntax for every `.ps1`, `.psm1`, and `.psd1` file.
- PSScriptAnalyzer error-level findings using `PSScriptAnalyzerSettings.psd1`.
- Bash syntax for every Linux shell script.
- ShellCheck error-level findings.
- Linux `--help` and `--dry-run` safety smoke tests.

The AI refactor workflow is manual-only to avoid surprise API usage and automatic hourly write attempts.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
