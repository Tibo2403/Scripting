param(
    [int]$DaysInactive = 90,
    [switch]$WhatIf
)

# Requires ActiveDirectory module
Import-Module ActiveDirectory

$limit = (Get-Date).AddDays(-$DaysInactive)

$inactiveUsers = Get-ADUser -Filter {LastLogonDate -lt $limit -and Enabled -eq $true} -Properties LastLogonDate

foreach ($user in $inactiveUsers) {
    Write-Host "Disabling user $($user.SamAccountName) last logon $($user.LastLogonDate)"
    Disable-ADAccount -Identity $user -WhatIf:$WhatIf
}
