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

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('start','stop','restart','status')]
    [string]$Action,
    [Parameter(Mandatory=$true)]
    [string]$ServiceName
)

switch ($Action.ToLower()) {
    'start'   { Start-Service   -Name $ServiceName }
    'stop'    { Stop-Service    -Name $ServiceName }
    'restart' { Restart-Service -Name $ServiceName }
    'status'  { Get-Service -Name $ServiceName | Format-List Name, Status }
}
