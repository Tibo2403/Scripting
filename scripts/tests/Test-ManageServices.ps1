# All service and remoting commands are simulated; no elevation or WinRM needed.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$serviceScript = Join-Path $PSScriptRoot '../powershell/ManageServices.ps1'
$calls = [System.Collections.Generic.List[string]]::new()
$simulation = @{ Failure = ''; RemoteCredential = $null }

function Get-Service {
    [CmdletBinding()]
    param([string]$Name)
    $calls.Add("get:$Name")
    if ($simulation.Failure -eq 'get') { Write-Error 'simulated missing service' }
    [pscustomobject]@{ Name = $Name; Status = 'Running' }
}
function Start-Service {
    [CmdletBinding()]
    param([object]$InputObject)
    $calls.Add("start:$($InputObject.Name)")
    if ($simulation.Failure -eq 'start') { Write-Error 'simulated start failure' }
}
function Stop-Service {
    [CmdletBinding()]
    param([object]$InputObject)
    $calls.Add("stop:$($InputObject.Name)")
    if ($simulation.Failure -eq 'stop') { Write-Error 'simulated stop failure' }
}
function Restart-Service {
    [CmdletBinding()]
    param([object]$InputObject)
    $calls.Add("restart:$($InputObject.Name)")
    if ($simulation.Failure -eq 'restart') { Write-Error 'simulated restart failure' }
}
function Invoke-Command {
    [CmdletBinding()]
    param([string]$ComputerName, [pscredential]$Credential,
          [scriptblock]$ScriptBlock, [object[]]$ArgumentList)
    $calls.Add("remote:$ComputerName")
    $simulation.RemoteCredential = $Credential
    if ($simulation.Failure -eq 'remote') { Write-Error 'simulated connection failure' }
    & $ScriptBlock @ArgumentList
}
function Assert-Condition {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

foreach ($target in @('localhost', 'remote-example')) {
    foreach ($action in @('start', 'stop', 'restart', 'status')) {
        $calls.Clear()
        $result = @(& $serviceScript -Action $action -ServiceName alpha,beta -ComputerName $target -Confirm:$false)
        Assert-Condition ($result.Count -eq 2 -and $result[0].Name -eq 'alpha') 'Expected structured service results.'
        if ($action -ne 'status') {
            Assert-Condition ($calls.Contains("${action}:alpha")) 'Expected service operation.'
            $calls.Clear()
            & $serviceScript -Action $action -ServiceName alpha -ComputerName $target -WhatIf
            Assert-Condition ($calls.Count -eq 0) 'WhatIf must not contact or mutate services.'
        }
        foreach ($failure in @('get', $action, 'remote') | Select-Object -Unique) {
            if ($failure -eq 'status' -or ($failure -eq 'remote' -and $target -eq 'localhost')) { continue }
            $simulation.Failure = $failure
            $calls.Clear()
            $output = [System.Collections.Generic.List[object]]::new()
            $caught = $false
            try {
                & $serviceScript -Action $action -ServiceName alpha,beta -ComputerName $target -Confirm:$false |
                    ForEach-Object { $output.Add($_) }
            } catch { $caught = $_.Exception.Message -like '*simulated*' }
            Assert-Condition $caught "Expected propagated $failure failure."
            Assert-Condition ($output.Count -eq 0) 'Failure must not emit success output.'
            Assert-Condition (-not $calls.Contains('get:beta')) 'Must stop before the next service after a failure.'
            $simulation.Failure = ''
        }
    }
}
foreach ($invalid in @(' ', '*', 'alpha?')) {
    $calls.Clear()
    $caught = $false
    try { & $serviceScript -Action stop -ServiceName alpha,$invalid -ComputerName localhost -Confirm:$false }
    catch { $caught = $true }
    Assert-Condition ($caught -and $calls.Count -eq 0) 'Validate all names before any mutation.'
}
$credential = [pscredential]::new('test-user', (ConvertTo-SecureString 'test-only' -AsPlainText -Force))
& $serviceScript -Action status -ServiceName alpha -ComputerName remote-example -Credential $credential | Out-Null
Assert-Condition ($simulation.RemoteCredential -eq $credential) 'Remote credentials must be forwarded.'
$caught = $false
try { & $serviceScript -Action status -ServiceName alpha -ComputerName localhost -Credential $credential }
catch { $caught = $true }
Assert-Condition $caught 'Local credentials must not be silently ignored.'
Write-Output 'ManageServices simulated tests passed.'
