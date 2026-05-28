# Scripting Toolkit

[![Script Validation](https://github.com/Tibo2403/Scripting/actions/workflows/script-validation.yml/badge.svg)](https://github.com/Tibo2403/Scripting/actions/workflows/script-validation.yml)

Collection of PowerShell and Bash scripts for system administration, security checks, Microsoft 365 operations, Linux dependency checks, and authorized lab or pentest workflows.

## Legal Notice

Use the pentest scripts only on systems where you have explicit written authorization. Unauthorized scanning, exploitation, credential access, or data transfer can be illegal and harmful.

The scripts in `scripts/linux/pentest_*.sh`, `scan_wifi.sh`, and `stealth_post.sh` are intended for controlled labs, training environments, or sanctioned security assessments.

## Repository Structure

```text
scripts/
├── linux/
│   ├── check_dependencies.sh
│   ├── dependencies.conf
│   ├── pentest_discovery.sh
│   ├── pentest_verification.sh
│   ├── pentest_exploitation.sh
│   ├── scan_wifi.sh
│   ├── setup_api.sh
│   └── stealth_post.sh
└── powershell/
    ├── DiskUsageReport.ps1
    ├── ExchangeOnlineManagement.ps1
    ├── Get-SystemInfo.ps1
    ├── LinkCrawler.ps1
    ├── ManageServices.ps1
    ├── SecurityCheck.ps1
    ├── SharePointManagement.ps1
    ├── TeamsManagement.ps1
    ├── Test-ScriptSyntax.ps1
    ├── UserManagement.ps1
    └── VMManagement.ps1
```

`targets.txt` contains example targets used by the pentest scripts. Keep it limited to systems that you are allowed to test.

## Prerequisites

- PowerShell 5.1+ or PowerShell 7+ for Windows scripts.
- Linux shell tools for Bash scripts.
- Optional tools depending on the script: `nmap`, `gvm-cli`, `curl`, `gpg`, `pwsh`.
- Optional PowerShell modules: Hyper-V, ExchangeOnlineManagement, MicrosoftTeams, PnP.PowerShell.
- Administrator or root privileges for scripts that manage services, users, VMs, network scans, or security settings.

## Quick Checks

Validate PowerShell syntax:

```powershell
.\scripts\powershell\Test-ScriptSyntax.ps1 -Path .\scripts\powershell
```

Validate Bash syntax from Linux, WSL, Git Bash, or CI:

```bash
find scripts/linux -name "*.sh" -print0 | xargs -0 -n1 bash -n
```

Check Linux dependencies:

```bash
bash scripts/linux/check_dependencies.sh
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
bash scripts/linux/pentest_discovery.sh
bash scripts/linux/pentest_verification.sh
bash scripts/linux/pentest_exploitation.sh
```

For `stealth_post.sh`, pass credentials through environment variables or a local config file that is never committed:

```bash
export FTP_USER="user"
export FTP_PASS="password"
export FTP_HOST="example.com"
export FTP_PATH="uploads/sysinfo.txt.gpg"
export GPG_PASSPHRASE="secret_passphrase"
bash scripts/linux/stealth_post.sh
```

## CI

The `script-validation.yml` workflow checks:

- PowerShell syntax for every `.ps1`, `.psm1`, and `.psd1` file.
- Bash syntax for every Linux shell script.

The AI refactor workflow is manual-only to avoid surprise API usage and automatic hourly write attempts.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
