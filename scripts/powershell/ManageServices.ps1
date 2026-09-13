<#
.SYNOPSIS
    Starts, stops, restarts or checks Windows services locally or through WinRM.
.DESCRIPTION
    Returns service objects and stops on the first failure. An uncaught error
    returns a non-zero exit code with powershell/pwsh -File. Mutations require
    appropriate service permissions (usually elevation); status does not.
.PARAMETER ComputerName
    Target computer. Remote operations require PowerShell remoting (WinRM).
.PARAMETER Credential
    Optional remote credentials. Not supported for local operations.
.EXAMPLE
    .\ManageServices.ps1 -Action status -ServiceName spooler
.EXAMPLE
    .\ManageServices.ps1 -Action restart -ServiceName spooler -WhatIf
.EXAMPLE
    .\ManageServices.ps1 -Action stop -ServiceName spooler -ComputerName SERVER01 -Credential (Get-Credential)
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Action,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string[]]$ServiceName,
    [ValidateNotNullOrEmpty()]
    [string]$ComputerName = $env:COMPUTERNAME,
    [PSCredential]$Credential
)

$ErrorActionPreference = 'Stop'
$isLocal = $ComputerName -in @('.', 'localhost', $env:COMPUTERNAME)
if ($isLocal -and $Credential) {
    throw 'Credential is only supported for remote computers.'
}
foreach ($name in $ServiceName) {
    if ([string]::IsNullOrWhiteSpace($name) -or [WildcardPattern]::ContainsWildcardCharacters($name)) {
        throw 'ServiceName must contain exact, non-empty service names without wildcards.'
    }
}

# Run the same operation locally or inside the authenticated remote session.
$operation = {
    param([string]$Name, [string]$RequestedAction)
    $service = Get-Service -Name $Name -ErrorAction Stop
    switch ($RequestedAction) {
        'start' { Start-Service -InputObject $service -ErrorAction Stop }
        'stop' { Stop-Service -InputObject $service -ErrorAction Stop }
        'restart' { Restart-Service -InputObject $service -ErrorAction Stop }
    }
    Get-Service -Name $Name -ErrorAction Stop
}

foreach ($name in $ServiceName) {
    if ($Action -ne 'status' -and -not $PSCmdlet.ShouldProcess("$name on $ComputerName", $Action)) {
        continue
    }
    try {
        if ($isLocal) {
            & $operation $name $Action
        } else {
            $remoteParameters = @{
                ComputerName = $ComputerName
                ScriptBlock = $operation
                ArgumentList = @($name, $Action)
                ErrorAction = 'Stop'
            }
            if ($Credential) { $remoteParameters.Credential = $Credential }
            Invoke-Command @remoteParameters
        }
    } catch {
        throw "Failed to $Action service '$name' on ${ComputerName}: $($_.Exception.Message)"
    }
}
