# PowerShell Scripts

This directory contains PowerShell scripts for Windows administration, Microsoft 365 operations, security checks, and local automation.

## Scripts

- `DiskUsageReport.ps1` - generates a disk usage report.
- `ExchangeOnlineManagement.ps1` - manages common Exchange Online operations.
- `Get-SystemInfo.ps1` - displays local system information.
- `LinkCrawler.ps1` - crawls links from a website.
- `ManageServices.ps1` - manages Windows services.
- `SecurityCheck.ps1` - checks selected security settings.
- `SharePointManagement.ps1` - automates SharePoint Online or on-premises actions.
- `TeamsManagement.ps1` - manages Microsoft Teams resources.
- `Test-ScriptSyntax.ps1` - validates PowerShell script syntax.
- `UserManagement.ps1` - manages local users.
- `VMManagement.ps1` - manages Hyper-V virtual machines.

## Validation

```powershell
.\Test-ScriptSyntax.ps1 -Path .
```

## Notes

`ManageServices.ps1` supports Windows PowerShell 5.1 and PowerShell 7 on Windows.
It returns service objects and stops on the first failure (non-zero exit with
`powershell/pwsh -File`). Local status queries do not require elevation; changes
require service permissions, usually an elevated session. Remote operations use
WinRM for both queries and changes; configure PowerShell remoting on the target.
`-Credential` is accepted only for remote targets. Use exact service names:
wildcards and blank names are rejected before any operation.

```powershell
.\scripts\powershell\ManageServices.ps1 -Action restart -ServiceName spooler -WhatIf
.\scripts\tests\Test-ManageServices.ps1 # Simulated; does not change real services
```

The commands above run from the repository root. `-WhatIf` prevents service changes
and remote connections for mutations. `status` always returns objects for inspection.

- Use elevated PowerShell sessions for scripts that manage services, local users, or Hyper-V.
- Review each script's parameter block and help before running it in production.
- Avoid committing tenant names, user exports, access tokens, or generated reports that contain sensitive data.
