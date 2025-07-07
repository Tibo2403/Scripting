<#
.SYNOPSIS
    Manages Exchange Online mailboxes.
.DESCRIPTION
    Connects to Exchange Online and allows you to list mailboxes,
    create a mailbox, add or remove aliases, and disconnect.
.PARAMETER Action
    Action to perform: connect, list, create, addalias, removealias, disconnect.
.PARAMETER UserPrincipalName
    User mailbox UPN (required for create, addalias, and removealias).
.PARAMETER Alias
    Alias to add or remove when using addalias or removealias.
.EXAMPLE
    PS> .\ExchangeOnlineManagement.ps1 -Action list
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('connect','list','create','addalias','removealias','disconnect')]
    [string]$Action,
    [string]$UserPrincipalName,
    [string]$Alias
)

# Ensure module is available
if (-not (Get-Module -ListAvailable -Name ExchangeOnlineManagement)) {
    Write-Error 'Exchange Online module is not installed. Install-Module ExchangeOnlineManagement'
    return
}

try {
    Import-Module ExchangeOnlineManagement -ErrorAction Stop
} catch {
    Write-Error "Failed to import Exchange Online module. $_"
    return
}

switch ($Action.ToLower()) {
    'connect' {
        try {
            Connect-ExchangeOnline -ErrorAction Stop | Out-Null
            Write-Output 'Connected to Exchange Online.'
        } catch {
            Write-Error "Failed to connect. $_"
        }
    }
    'list' {
        Get-Mailbox
    }
    'create' {
        if (-not $UserPrincipalName) {
            Write-Error 'UserPrincipalName is required to create a mailbox.'
            break
        }
        try {
            New-Mailbox -UserPrincipalName $UserPrincipalName -ErrorAction Stop
            Write-Output "Mailbox for $UserPrincipalName created."
        } catch {
            Write-Error "Failed to create mailbox. $_"
        }
    }
    'addalias' {
        if (-not $UserPrincipalName -or -not $Alias) {
            Write-Error 'UserPrincipalName and Alias are required to add an alias.'
            break
        }
        try {
            Set-Mailbox -Identity $UserPrincipalName -EmailAddresses @{add=$Alias} -ErrorAction Stop
            Write-Output "Added alias $Alias to $UserPrincipalName."
        } catch {
            Write-Error "Failed to add alias. $_"
        }
    }
    'removealias' {
        if (-not $UserPrincipalName -or -not $Alias) {
            Write-Error 'UserPrincipalName and Alias are required to remove an alias.'
            break
        }
        try {
            Set-Mailbox -Identity $UserPrincipalName -EmailAddresses @{remove=$Alias} -ErrorAction Stop
            Write-Output "Removed alias $Alias from $UserPrincipalName."
        } catch {
            Write-Error "Failed to remove alias. $_"
        }
    }
    'disconnect' {
        Disconnect-ExchangeOnline -Confirm:$false
    }
}
