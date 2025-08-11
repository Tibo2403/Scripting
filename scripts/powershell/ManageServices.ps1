#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Starts, stops, restarts or checks the status of a Windows service.
.DESCRIPTION
    Allows simple service management by passing an action and service name.
    The script wraps standard service cmdlets for quick usage.
.PARAMETER Action
    The operation to perform: start, stop, restart or status.
.PARAMETER ServiceName
    Name of the service to manage.
.EXAMPLE
    PS> .\ManageServices.ps1 -Action status -ServiceName spooler
    Retrieves the status of the Print Spooler service.
.EXAMPLE
    PS> .\ManageServices.ps1 -Action restart -ServiceName wuauserv
    Restarts the Windows Update service.
#>

[CmdletBinding(SupportsShouldProcess=$true)]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('start','stop','restart','status')]
    [string]$Action,
    [Parameter(Mandatory=$true)]
    [string]$ServiceName
)

try {
    $service = Get-Service -Name $ServiceName -ErrorAction Stop
} catch {
    Write-Error "Service '$ServiceName' was not found."
    return
}

try {
    switch ($Action.ToLower()) {
        'start' {
            if ($PSCmdlet.ShouldProcess($ServiceName, $Action)) {
                Start-Service -InputObject $service
                Write-Output "Service '$ServiceName' started successfully."
            }
        }
        'stop' {
            if ($PSCmdlet.ShouldProcess($ServiceName, $Action)) {
                Stop-Service -InputObject $service
                Write-Output "Service '$ServiceName' stopped successfully."
            }
        }
        'restart' {
            if ($PSCmdlet.ShouldProcess($ServiceName, $Action)) {
                Restart-Service -InputObject $service
                Write-Output "Service '$ServiceName' restarted successfully."
            }
        }
        'status' {
            if ($PSCmdlet.ShouldProcess($ServiceName, $Action)) {
                $service | Format-List Name, Status
                Write-Output "Service '$ServiceName' status retrieved successfully."
            }
        }
    }
} catch {
    Write-Error "Failed to $Action service '$ServiceName'. $_"
}
