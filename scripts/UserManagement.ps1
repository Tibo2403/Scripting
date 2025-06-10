<#
.SYNOPSIS
    Creates, removes or lists local user accounts.
#>

param(
    [ValidateSet('create','delete','list')]
    [string]$Action = 'list',
    [string]$UserName,
    [string]$Password
)

switch ($Action.ToLower()) {
    'create' {
        if (-not $UserName -or -not $Password) {
            Write-Error 'UserName and Password are required to create a user.'
            break
        }
        if (Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue) {
            Write-Error "User '$UserName' already exists."
            break
        }
        $secure = ConvertTo-SecureString $Password -AsPlainText -Force
        New-LocalUser -Name $UserName -Password $secure
    }
    'delete' {
        if (-not $UserName) {
            Write-Error 'UserName is required to delete a user.'
            break
        }
        if (-not (Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue)) {
            Write-Error "User '$UserName' does not exist."
            break
        }
        Remove-LocalUser -Name $UserName
    }
    'list' {
        Get-LocalUser
    }
}
