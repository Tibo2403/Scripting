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

function Invoke-ServiceAction {
    [CmdletBinding(SupportsShouldProcess=$true)]
    param(
        [Parameter(Mandatory=$true, ValueFromPipeline=$true)]
        [string]$Name,
        [Parameter(Mandatory=$true)]
        [ValidateSet('start','stop')]
        [string]$Action,
        [string]$ComputerName = $env:COMPUTERNAME,
        [PSCredential]$Credential
    )
    process {
        try {
            if ($Credential) {
                Get-Service -Name $Name -ComputerName $ComputerName -Credential $Credential -ErrorAction Stop | Out-Null
            } else {
                Get-Service -Name $Name -ComputerName $ComputerName -ErrorAction Stop | Out-Null
            }
        } catch {
            Write-Error "Service '$Name' was not found on $ComputerName."
            return
        }

        if ($PSCmdlet.ShouldProcess("$Name on $ComputerName", $Action)) {
            try {
                if ($ComputerName -eq $env:COMPUTERNAME) {
                    if ($Action -eq 'start') {
                        Start-Service -Name $Name
                    } else {
                        Stop-Service -Name $Name
                    }
                } else {
                    $scriptBlock = {
                        param($svcName, $svcAction)
                        if ($svcAction -eq 'start') {
                            Start-Service -Name $svcName
                        } else {
                            Stop-Service -Name $svcName
                        }
                    }
                    if ($Credential) {
                        Invoke-Command -ComputerName $ComputerName -Credential $Credential -ScriptBlock $scriptBlock -ArgumentList $Name,$Action
                    } else {
                        Invoke-Command -ComputerName $ComputerName -ScriptBlock $scriptBlock -ArgumentList $Name,$Action
                    }
                }
                Write-Output "Service '$Name' $($Action + 'ed') successfully on $ComputerName."
            } catch {
                Write-Error "Failed to $Action service '$Name' on $ComputerName. $_"
            }
        }
    }
}

switch ($Action.ToLower()) {
    'start' {
        $ServiceName | Invoke-ServiceAction -Action 'start' -ComputerName $ComputerName -Credential $Credential
    }
    'stop' {
        $ServiceName | Invoke-ServiceAction -Action 'stop' -ComputerName $ComputerName -Credential $Credential
    }
    'restart' {
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

            if ($PSCmdlet.ShouldProcess("$name on $ComputerName", $Action)) {
                try {
                    if ($ComputerName -eq $env:COMPUTERNAME) {
                        Restart-Service -InputObject $service
                    } else {
                        if ($Credential) {
                            Invoke-Command -ComputerName $ComputerName -Credential $Credential -ScriptBlock { Restart-Service -Name $using:name }
                        } else {
                            Invoke-Command -ComputerName $ComputerName -ScriptBlock { Restart-Service -Name $using:name }
                        }
                    }
                    Write-Output "Service '$name' restarted successfully on $ComputerName."
                } catch {
                    Write-Error "Failed to restart service '$name' on $ComputerName. $_"
                }
            }
        }
    }
    'status' {
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

            if ($PSCmdlet.ShouldProcess("$name on $ComputerName", $Action)) {
                $service | Format-List Name, Status
                Write-Output "Service '$name' status retrieved successfully on $ComputerName."
            }
        }
    }
}
