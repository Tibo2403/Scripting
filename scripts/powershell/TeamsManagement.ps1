<#
.SYNOPSIS
    Manages Microsoft Teams.
.DESCRIPTION
    Allows listing teams, creating a new team, and adding or removing users from a team
    using the Microsoft Teams PowerShell module.
.PARAMETER Action
    Operation to perform: list, create, adduser or removeuser.
.PARAMETER TeamName
    Name of the team for create, adduser or removeuser actions.
.PARAMETER User
    UPN of the user to add or remove.
.EXAMPLE
    PS> .\TeamsManagement.ps1 -Action list
    Lists all Microsoft Teams.
.EXAMPLE
    PS> .\TeamsManagement.ps1 -Action create -TeamName "Marketing"
    Creates a new team named 'Marketing'.
.EXAMPLE
    PS> .\TeamsManagement.ps1 -Action adduser -TeamName "Marketing" -User bob@example.com
    Adds the user to the specified team.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('list','create','adduser','removeuser')]
    [string]$Action,
    [string]$TeamName,
    [string]$User
)

try {
    if (-not (Get-Module -ListAvailable -Name MicrosoftTeams)) {
        Write-Error 'Microsoft Teams module is not installed. Install-Module -Name MicrosoftTeams'
        return
    }
    Import-Module MicrosoftTeams -ErrorAction Stop
} catch {
    Write-Error "Failed to import Microsoft Teams module. $_"
    return
}

try {
    Connect-MicrosoftTeams -ErrorAction Stop | Out-Null
} catch {
    Write-Error "Failed to connect to Microsoft Teams. $_"
    return
}

switch ($Action.ToLower()) {
    'list' {
        Get-Team
    }
    'create' {
        if (-not $TeamName) {
            Write-Error 'TeamName is required to create a team.'
            break
        }
        try {
            New-Team -DisplayName $TeamName -ErrorAction Stop
            Write-Output "Team '$TeamName' created."
        } catch {
            Write-Error "Failed to create team '$TeamName'. $_"
        }
    }
    'adduser' {
        if (-not $TeamName -or -not $User) {
            Write-Error 'TeamName and User are required to add a user.'
            break
        }
        try {
            $team = Get-Team -DisplayName $TeamName -ErrorAction Stop
            Add-TeamUser -GroupId $team.GroupId -User $User -ErrorAction Stop
            Write-Output "Added $User to '$TeamName'."
        } catch {
            Write-Error "Failed to add $User to '$TeamName'. $_"
        }
    }
    'removeuser' {
        if (-not $TeamName -or -not $User) {
            Write-Error 'TeamName and User are required to remove a user.'
            break
        }
        try {
            $team = Get-Team -DisplayName $TeamName -ErrorAction Stop
            Remove-TeamUser -GroupId $team.GroupId -User $User -ErrorAction Stop
            Write-Output "Removed $User from '$TeamName'."
        } catch {
            Write-Error "Failed to remove $User from '$TeamName'. $_"
        }
    }
}
