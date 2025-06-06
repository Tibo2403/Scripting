param(
    [int]$DaysInactive = 90,
    [string]$OrganizationalUnit,
    [string]$ReportPath,
    [switch]$WhatIf
)

# Requires ActiveDirectory module
Import-Module ActiveDirectory

$limit = (Get-Date).AddDays(-$DaysInactive)

$params = @{Filter = {LastLogonDate -lt $limit -and Enabled -eq $true}; Properties = 'LastLogonDate'}
if ($OrganizationalUnit) { $params['SearchBase'] = $OrganizationalUnit }

$inactiveUsers = Get-ADUser @params

if ($ReportPath) {
    $inactiveUsers |
        Select-Object Name, SamAccountName, LastLogonDate |
        Export-Csv -Path $ReportPath -NoTypeInformation
}

foreach ($user in $inactiveUsers) {
    Write-Host "Disabling user $($user.SamAccountName) last logon $($user.LastLogonDate)"
    Disable-ADAccount -Identity $user -WhatIf:$WhatIf
}

Write-Host "Disabled $($inactiveUsers.Count) account(s)" -ForegroundColor Green
