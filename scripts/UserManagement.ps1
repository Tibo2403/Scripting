<#
.SYNOPSIS
    Creates, removes or lists local user accounts.
.DESCRIPTION
    Provides simple management of local users. You can create a new account,
    remove an existing one or list all local users.
.PARAMETER Action
    Action to perform: create, delete or list. Defaults to list.
.PARAMETER UserName
    Name of the user account to create or delete.
.PARAMETER Password
    Password for the new account when using the create action.
.EXAMPLE
    PS> .\UserManagement.ps1 -Action list
    Lists all local user accounts.
.EXAMPLE
    PS> .\UserManagement.ps1 -Action create -UserName alice -Password P@ssw0rd
    Creates a user named 'alice' with the specified password.
.EXAMPLE
    PS> .\UserManagement.ps1 -Action delete -UserName alice
    Removes the user account named 'alice'.
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
        $secure = ConvertTo-SecureString $Password -AsPlainText -Force
        New-LocalUser -Name $UserName -Password $secure
    }
    'delete' {
        if (-not $UserName) {
            Write-Error 'UserName is required to delete a user.'
            break
        }
        Remove-LocalUser -Name $UserName
    }
    'list' {
        Get-LocalUser
    }
}
