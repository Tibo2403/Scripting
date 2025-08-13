#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Creates, removes, lists, imports, or exports local user accounts.
.DESCRIPTION
    Provides simple management of local users. You can create a new account,
    remove an existing one, list all local users, import users from an Excel or
    CSV file, or export them to a file.
.PARAMETER Action
    Action to perform: create, delete, list, import or export. Defaults to list.
.PARAMETER UserName
    Name of the user account to create or delete.
.PARAMETER Password
    Secure password for the new account when using the create action. If not
    supplied, you will be prompted to enter one.
.PARAMETER ExcelPath
    Path to an Excel (xlsx) or CSV file containing 'UserName' and 'Password'
    columns when using the import action.
.PARAMETER ExportPath
    Path to an Excel (xlsx) or CSV file to receive exported user information
    when using the export action.
.EXAMPLE
    PS> .\UserManagement.ps1 -Action list
    Lists all local user accounts.
.EXAMPLE
    PS> .\UserManagement.ps1 -Action create -UserName alice -Password (Read-Host -AsSecureString)
    Prompts for a secure password and creates a user named 'alice'.
.EXAMPLE
    PS> .\UserManagement.ps1 -Action delete -UserName alice
    Removes the user account named 'alice'.
.EXAMPLE
    PS> .\UserManagement.ps1 -Action import -ExcelPath users.xlsx
    Imports users listed in an Excel or CSV file with 'UserName' and 'Password' columns.
.EXAMPLE
    PS> .\UserManagement.ps1 -Action export -ExportPath users.csv
    Exports all local users to a CSV or Excel file.
#>

param(
    [ValidateSet('create','delete','list','import','export')]
    [string]$Action = 'list',
    [string]$UserName,
    [SecureString]$Password,
    [string]$ExcelPath,
    [string]$ExportPath
)

switch ($Action.ToLower()) {
    'create' {
        if (-not $UserName) {
            Write-Error 'UserName is required to create a user.'
            break
        }
        if (-not $Password) {
            $Password = Read-Host -Prompt 'Enter password' -AsSecureString
        }
        if (-not $Password) {
            Write-Error 'Password is required to create a user.'
            break
        }
        if (Get-LocalUser -Name $UserName -ErrorAction SilentlyContinue) {
            Write-Error "User '$UserName' already exists."
            break
        }
        New-LocalUser -Name $UserName -Password $Password
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
    'import' {
        if (-not $ExcelPath) {
            Write-Error 'ExcelPath is required to import users.'
            break
        }
        if (-not (Test-Path $ExcelPath)) {
            Write-Error "File '$ExcelPath' not found."
            break
        }

        $users = @()
        if ($ExcelPath -match '\.xlsx$') {
            if (-not (Get-Module -ListAvailable -Name ImportExcel)) {
                Write-Error 'The ImportExcel module is required to read Excel files.'
                break
            }
            $users = Import-Excel -Path $ExcelPath
        } else {
            $users = Import-Csv -Path $ExcelPath
        }

        foreach ($u in $users) {
            $name = $u.UserName
            $pwdText = $u.Password
            if (-not $name -or -not $pwdText) {
                Write-Warning 'Skipping entry missing UserName or Password.'
                continue
            }
            if (Get-LocalUser -Name $name -ErrorAction SilentlyContinue) {
                Write-Warning "User '$name' already exists. Skipping."
                continue
            }
            $secPwd = ConvertTo-SecureString $pwdText -AsPlainText -Force
            New-LocalUser -Name $name -Password $secPwd
        }
    }
    'export' {
        if (-not $ExportPath) {
            Write-Error 'ExportPath is required to export users.'
            break
        }
        $users = Get-LocalUser
        if ($ExportPath -match '\.xlsx$') {
            if (-not (Get-Module -ListAvailable -Name ImportExcel)) {
                Write-Error 'The ImportExcel module is required to write Excel files.'
                break
            }
            $users | Export-Excel -Path $ExportPath -AutoSize
        } else {
            $users | Export-Csv -Path $ExportPath -NoTypeInformation
        }
    }
}
