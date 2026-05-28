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

- Use elevated PowerShell sessions for scripts that manage services, local users, or Hyper-V.
- Review each script's parameter block and help before running it in production.
- Avoid committing tenant names, user exports, access tokens, or generated reports that contain sensitive data.
