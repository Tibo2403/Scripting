<#
.SYNOPSIS
    Starts, stops, restarts or checks the status of a Windows service.
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
