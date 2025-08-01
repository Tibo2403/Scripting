<#
.SYNOPSIS
    Manages Microsoft Teams.
.DESCRIPTION
    Allows listing teams, creating or deleting a team, managing members and owners,
    creating channels, exporting membership information and performing bulk
    operations using the Microsoft Teams PowerShell module.
.PARAMETER Action
    Operation to perform: list, create, delete, adduser, removeuser, addowner,
    createchannel, export or bulkadd.
.PARAMETER TeamName
    Name of the team for actions that require a team.
.PARAMETER User
    UPN of the user to add, remove or assign as owner.
.PARAMETER ChannelName
    Name of the channel when using the createchannel action.
.PARAMETER CsvPath
    Path to a CSV file for bulkadd or export actions.
.EXAMPLE
    PS> .\TeamsManagement.ps1 -Action list
    Lists all Microsoft Teams.
.EXAMPLE
    PS> .\TeamsManagement.ps1 -Action create -TeamName "Marketing"
    Creates a new team named 'Marketing'.
.EXAMPLE
    PS> .\TeamsManagement.ps1 -Action adduser -TeamName "Marketing" -User bob@example.com
    Adds the user to the specified team.
.EXAMPLE
    PS> .\TeamsManagement.ps1 -Action delete -TeamName "Old Team"
    Deletes the specified team.
.EXAMPLE
    PS> .\TeamsManagement.ps1 -Action addowner -TeamName "Marketing" -User alice@example.com
    Gives ownership of the team to the specified user.
.EXAMPLE
    PS> .\TeamsManagement.ps1 -Action createchannel -TeamName "Marketing" -ChannelName "Général"
    Creates a new channel named 'Général'.
.EXAMPLE
    PS> .\TeamsManagement.ps1 -Action bulkadd -TeamName "Marketing" -CsvPath .\users.csv
    Adds all users listed in the CSV file to the team.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('list','create','delete','adduser','removeuser','addowner','createchannel','export','bulkadd')]
    [string]$Action,
    [string]$TeamName,
    [string]$User,
    [string]$ChannelName,
    [string]$CsvPath
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
    'delete' {
        if (-not $TeamName) {
            Write-Error 'TeamName is required to delete a team.'
            break
        }
        try {
            $team = Get-Team -DisplayName $TeamName -ErrorAction Stop
            Remove-Team -GroupId $team.GroupId -ErrorAction Stop
            Write-Output "Team '$TeamName' deleted."
        } catch {
            Write-Error "Failed to delete team '$TeamName'. $_"
        }
    }
    'adduser' {
        if (-not $TeamName) {
            Write-Error 'TeamName is required to add a user.'
            break
        }
        $userList = @()
        if ($CsvPath) {
            if (-not (Test-Path $CsvPath)) {
                Write-Error "CSV file '$CsvPath' not found."
                break
            }
            $userList = (Import-Csv -Path $CsvPath).User
        } elseif ($User) {
            $userList = @($User)
        } else {
            Write-Error 'User or CsvPath is required to add a user.'
            break
        }
        try {
            $team = Get-Team -DisplayName $TeamName -ErrorAction Stop
            foreach ($u in $userList) {
                try {
                    Add-TeamUser -GroupId $team.GroupId -User $u -ErrorAction Stop
                    Write-Output "Added $u to '$TeamName'."
                } catch {
                    Write-Error "Failed to add $u to '$TeamName'. $_"
                }
            }
        } catch {
            Write-Error "Failed to add users to '$TeamName'. $_"
        }
    }
    'removeuser' {
        if (-not $TeamName) {
            Write-Error 'TeamName is required to remove a user.'
            break
        }
        $userList = @()
        if ($CsvPath) {
            if (-not (Test-Path $CsvPath)) {
                Write-Error "CSV file '$CsvPath' not found."
                break
            }
            $userList = (Import-Csv -Path $CsvPath).User
        } elseif ($User) {
            $userList = @($User)
        } else {
            Write-Error 'User or CsvPath is required to remove a user.'
            break
        }
        try {
            $team = Get-Team -DisplayName $TeamName -ErrorAction Stop
            foreach ($u in $userList) {
                try {
                    Remove-TeamUser -GroupId $team.GroupId -User $u -ErrorAction Stop
                    Write-Output "Removed $u from '$TeamName'."
                } catch {
                    Write-Error "Failed to remove $u from '$TeamName'. $_"
                }
            }
        } catch {
            Write-Error "Failed to remove users from '$TeamName'. $_"
        }
    }
    'addowner' {
        if (-not $TeamName -or -not $User) {
            Write-Error 'TeamName and User are required to add an owner.'
            break
        }
        try {
            $team = Get-Team -DisplayName $TeamName -ErrorAction Stop
            Add-TeamUser -GroupId $team.GroupId -User $User -Role Owner -ErrorAction Stop
            Write-Output "Added owner $User to '$TeamName'."
        } catch {
            Write-Error "Failed to add owner $User to '$TeamName'. $_"
        }
    }
    'createchannel' {
        if (-not $TeamName -or -not $ChannelName) {
            Write-Error 'TeamName and ChannelName are required to create a channel.'
            break
        }
        try {
            $team = Get-Team -DisplayName $TeamName -ErrorAction Stop
            New-TeamChannel -GroupId $team.GroupId -DisplayName $ChannelName -ErrorAction Stop
            Write-Output "Channel '$ChannelName' created in '$TeamName'."
        } catch {
            Write-Error "Failed to create channel '$ChannelName' in '$TeamName'. $_"
        }
    }
    'export' {
        if (-not $CsvPath) {
            Write-Error 'CsvPath is required to export teams.'
            break
        }
        $results = @()
        foreach ($t in Get-Team) {
            foreach ($u in Get-TeamUser -GroupId $t.GroupId) {
                $results += [PSCustomObject]@{ Team = $t.DisplayName; User = $u.User; Role = $u.Role }
            }
        }
        $results | Export-Csv -Path $CsvPath -NoTypeInformation
        Write-Output "Exported team membership to '$CsvPath'."
    }
    'bulkadd' {
        if (-not $TeamName -or -not $CsvPath) {
            Write-Error 'TeamName and CsvPath are required for bulkadd.'
            break
        }
        if (-not (Test-Path $CsvPath)) {
            Write-Error "CSV file '$CsvPath' not found."
            break
        }
        try {
            $team = Get-Team -DisplayName $TeamName -ErrorAction Stop
            $userList = (Import-Csv -Path $CsvPath).User
            foreach ($u in $userList) {
                try {
                    Add-TeamUser -GroupId $team.GroupId -User $u -ErrorAction Stop
                    Write-Output "Added $u to '$TeamName'."
                } catch {
                    Write-Error "Failed to add $u to '$TeamName'. $_"
                }
            }
        } catch {
            Write-Error "Failed bulk add operation. $_"
        }
    }
}
} catch {
    Write-Error "Failed to execute Teams action. $_"
} finally {
    Disconnect-MicrosoftTeams | Out-Null
}
