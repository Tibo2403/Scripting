# Compatibility Matrix

| Script | OS | Privileges | Required tools/modules | Risk | Dry-run |
| --- | --- | --- | --- | --- | --- |
| `scripts/linux/check_dependencies.sh` | Linux | Optional sudo for `--install` | package manager, optional `pwsh` | Low | Not needed |
| `scripts/linux/setup_api.sh` | Debian/Ubuntu Linux | root | `apt-get`, `curl`, `python3`, network | Medium | `--offline` |
| `scripts/linux/pentest_discovery.sh` | Linux | root recommended | `nmap` | High | Yes |
| `scripts/linux/pentest_verification.sh` | Linux | root recommended | `nmap`, `msfconsole`, optional `gvm-cli` | High | Yes |
| `scripts/linux/pentest_exploitation.sh` | Linux | depends on assessment | optional `searchsploit` | High | Yes |
| `scripts/linux/scan_wifi.sh` | Linux | root | aircrack-ng suite | High | Yes |
| `scripts/linux/stealth_post.sh` | Linux | user context | `gpg`, `curl`, `shred` | High | Yes |
| `scripts/powershell/DiskUsageReport.ps1` | Windows | user/admin depending path | SMTP optional | Low | `-WhatIf` for email |
| `scripts/powershell/Get-SystemInfo.ps1` | Windows | user | built-in PowerShell | Low | Not needed |
| `scripts/powershell/ManageServices.ps1` | Windows | admin for state changes | built-in PowerShell | Medium | `-WhatIf` |
| `scripts/powershell/VMManagement.ps1` | Windows | admin | Hyper-V module | Medium | Manual review |
| `scripts/powershell/LinkCrawler.ps1` | Windows/Linux PowerShell | user | optional ThreadJob, SMTP, BurntToast | Low | `-WhatIf` for notifications |
| `scripts/powershell/TeamsManagement.ps1` | Windows/Linux PowerShell | Microsoft 365 role | MicrosoftTeams module | Medium | Manual review |
| `scripts/powershell/ExchangeOnlineManagement.ps1` | Windows/Linux PowerShell | Microsoft 365 role | ExchangeOnlineManagement module | Medium | Manual review |
| `scripts/powershell/SharePointManagement.ps1` | Windows/Linux PowerShell | SharePoint admin | SharePoint modules | Medium | Manual review |
| `scripts/powershell/UserManagement.ps1` | Windows | admin | LocalAccounts, optional ImportExcel, encrypted import passwords | High | `-WhatIf` |
| `scripts/powershell/SecurityCheck.ps1` | Windows | user/admin depending check | built-in PowerShell | Low | Not needed |

High-risk scripts require explicit authorization before use. Prefer `--dry-run` or `-WhatIf` where available, and keep generated outputs out of commits.
