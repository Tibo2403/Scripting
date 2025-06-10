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

[CmdletBinding()]
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
        'start'   { Start-Service   -InputObject $service }
        'stop'    { Stop-Service    -InputObject $service }
        'restart' { Restart-Service -InputObject $service }
        'status'  { $service | Format-List Name, Status }
    }
} catch {
    Write-Error "Failed to $Action service '$ServiceName'. $_"
}
