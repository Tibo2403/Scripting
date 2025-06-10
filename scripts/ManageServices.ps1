<#
.SYNOPSIS
    Starts, stops, restarts or checks the status of a Windows service.
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
