<#
.SYNOPSIS
    Manages Exchange Online mailboxes.
.DESCRIPTION
    Connects to Exchange Online and allows you to list mailboxes,
    create a mailbox, manage aliases, quotas, forwarding and
    disconnect from the session.
.PARAMETER Action
    Action to perform: connect, list, create, addalias, removealias,
    setquota, setforward, setsendas, usage, disconnect.
.PARAMETER UserPrincipalName
    User mailbox UPN (required for create, addalias, removealias,
    setquota, setforward and setsendas).
.PARAMETER Alias
    Alias to add or remove when using addalias or removealias.
.PARAMETER Quota
    Quota size string (e.g. '50GB') used with setquota.
.PARAMETER ForwardAddress
    SMTP address used with setforward.
.PARAMETER SendAsUser
    UPN granted Send-As rights when using setsendas.
.PARAMETER CsvPath
    Path of the CSV file for usage action. Defaults to .\mailbox_usage.csv.
.EXAMPLE
    PS> .\ExchangeOnlineManagement.ps1 -Action list
    Lists all mailboxes.
.EXAMPLE
    PS> .\ExchangeOnlineManagement.ps1 -Action setquota -UserPrincipalName user@example.com -Quota 50GB
    Sets the ProhibitSendQuota for the mailbox.
.EXAMPLE
    PS> .\ExchangeOnlineManagement.ps1 -Action setforward -UserPrincipalName user@example.com -ForwardAddress forward@example.com
    Forwards messages to another mailbox.
.EXAMPLE
    PS> .\ExchangeOnlineManagement.ps1 -Action usage -CsvPath usage.csv
    Exports mailbox statistics to a CSV file.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('connect','list','create','addalias','removealias','setquota','setforward','setsendas','usage','disconnect')]
    [string]$Action,
    [string]$UserPrincipalName,
    [string]$Alias,
    [string]$Quota,
    [string]$ForwardAddress,
    [string]$SendAsUser,
    [string]$CsvPath = '.\mailbox_usage.csv'
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
    'setquota' {
        if (-not $UserPrincipalName -or -not $Quota) {
            Write-Error 'UserPrincipalName and Quota are required to set quota.'
            break
        }
        try {
            Set-Mailbox -Identity $UserPrincipalName -ProhibitSendQuota $Quota -ErrorAction Stop
            Write-Output "Set quota for $UserPrincipalName to $Quota."
        } catch {
            Write-Error "Failed to set quota. $_"
        }
    }
    'setforward' {
        if (-not $UserPrincipalName -or -not $ForwardAddress) {
            Write-Error 'UserPrincipalName and ForwardAddress are required to set forwarding.'
            break
        }
        try {
            Set-Mailbox -Identity $UserPrincipalName -ForwardingAddress $ForwardAddress -ErrorAction Stop
            Write-Output "Forwarding for $UserPrincipalName set to $ForwardAddress."
        } catch {
            Write-Error "Failed to set forwarding. $_"
        }
    }
    'setsendas' {
        if (-not $UserPrincipalName -or -not $SendAsUser) {
            Write-Error 'UserPrincipalName and SendAsUser are required to grant send-as permission.'
            break
        }
        try {
            Add-RecipientPermission -Identity $UserPrincipalName -Trustee $SendAsUser -AccessRights SendAs -ErrorAction Stop
            Write-Output "Granted Send-As permission on $UserPrincipalName to $SendAsUser."
        } catch {
            Write-Error "Failed to grant Send-As permission. $_"
        }
    }
    'usage' {
        try {
            Get-MailboxStatistics | Select-Object DisplayName,ItemCount,TotalItemSize,LastLogonTime | Export-Csv -Path $CsvPath -NoTypeInformation -Encoding UTF8
            Write-Output "Mailbox usage exported to $CsvPath."
        } catch {
            Write-Error "Failed to export mailbox usage. $_"
        }
    }
    'disconnect' {
        Disconnect-ExchangeOnline -Confirm:$false
    }
}
