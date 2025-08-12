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
    One or more service names to manage.
.PARAMETER ComputerName
    Optional remote computer. Defaults to the local machine.
.PARAMETER Credential
    Optional credentials for accessing the remote computer.
.EXAMPLE
    PS> .\ManageServices.ps1 -Action status -ServiceName spooler
    Retrieves the status of the Print Spooler service.
.EXAMPLE
    PS> .\ManageServices.ps1 -Action restart -ServiceName wuauserv
    Restarts the Windows Update service.
.EXAMPLE
    PS> $cred = Get-Credential; .\ManageServices.ps1 -Action stop -ServiceName spooler,bits -ComputerName SERVER01 -Credential $cred
    Stops the Print Spooler and BITS services on SERVER01 using the specified credential.
#>

[CmdletBinding(SupportsShouldProcess=$true)]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('start','stop','restart','status')]
    [string]$Action,
    [Parameter(Mandatory=$true)]
    [string[]]$ServiceName,
    [string]$ComputerName = $env:COMPUTERNAME,
    [PSCredential]$Credential
)

foreach ($name in $ServiceName) {
    try {
        if ($Credential) {
            $service = Get-Service -Name $name -ComputerName $ComputerName -Credential $Credential -ErrorAction Stop
        } else {
            $service = Get-Service -Name $name -ComputerName $ComputerName -ErrorAction Stop
        }
    } catch {
        Write-Error "Service '$name' was not found on $ComputerName."
        continue
    }

    try {
        switch ($Action.ToLower()) {
            'start' {
                if ($PSCmdlet.ShouldProcess("$name on $ComputerName", $Action)) {
                    if ($Credential) {
                        Start-Service -InputObject $service -Credential $Credential
                    } else {
                        Start-Service -InputObject $service
                    }
                    Write-Output "Service '$name' started successfully on $ComputerName."
                }
            }
            'stop' {
                if ($PSCmdlet.ShouldProcess("$name on $ComputerName", $Action)) {
                    if ($Credential) {
                        Stop-Service -InputObject $service -Credential $Credential
                    } else {
                        Stop-Service -InputObject $service
                    }
                    Write-Output "Service '$name' stopped successfully on $ComputerName."
                }
            }
            'restart' {
                if ($PSCmdlet.ShouldProcess("$name on $ComputerName", $Action)) {
                    if ($Credential) {
                        Restart-Service -InputObject $service -Credential $Credential
                    } else {
                        Restart-Service -InputObject $service
                    }
                    Write-Output "Service '$name' restarted successfully on $ComputerName."
                }
            }
            'status' {
                if ($PSCmdlet.ShouldProcess("$name on $ComputerName", $Action)) {
                    $service | Format-List Name, Status
                    Write-Output "Service '$name' status retrieved successfully on $ComputerName."
                }
            }
        }
    } catch {
        Write-Error "Failed to $Action service '$name' on $ComputerName. $_"
    }
}
