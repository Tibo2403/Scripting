[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../Recovery.ps1')
$config = Get-Content (Join-Path $PSScriptRoot '../backup-config.json') -Raw | ConvertFrom-Json
$calls = [System.Collections.Generic.List[string]]::new()
$behavior = @{ FailRestore = ''; Repository = $true; Validation = $true }
$arguments = @{
    Configuration = $config
    RestoreService = {
        param($Service)
        $calls.Add($Service.name)
        if ($Service.name -eq $behavior.FailRestore) { throw 'simulated restore failure' }
    }
    TestRepository = { param($RepositoryHost) $calls.Add("repository:$RepositoryHost"); $behavior.Repository }
    TestValidation = { param($Test) $calls.Add("test:$($Test.name)"); $behavior.Validation }
    Log = { param($Message) $null = $Message }
}
function Assert-Equal {
    param($Actual, $Expected)
    if ($Actual -cne $Expected) { throw "Expected [$Expected], got [$Actual]" }
}
function Assert-Failure {
    param([scriptblock]$Action, [string]$Expected)
    try { & $Action } catch {
        if ($_.Exception.Message -notlike "*$Expected*") { throw }
        return
    }
    throw "Expected failure: $Expected"
}
# Deliberately reverse the input to verify priority ordering.
$config.recoveryPriority = @($config.recoveryPriority | Sort-Object order -Descending)
Invoke-PraRecovery @arguments
Assert-Equal ($calls -join ',') 'repository:nas-backup.local,ActiveDirectory,FileServer_Critique,ERP_SQL,CRM_App,test:SQL listener,test:Partage critique'
$calls.Clear()
Invoke-PraRecovery @arguments -Simulate
Assert-Equal $calls.Count 0
$behavior.Repository = $false
Assert-Failure { Invoke-PraRecovery @arguments } 'injoignable'
Assert-Equal $calls.Count 1
$calls.Clear()
$behavior.Repository = $true
$behavior.FailRestore = 'FileServer_Critique'
Assert-Failure { Invoke-PraRecovery @arguments } 'simulated restore failure'
Assert-Equal ($calls -join ',') 'repository:nas-backup.local,ActiveDirectory,FileServer_Critique'
$calls.Clear()
$behavior.FailRestore = ''
$behavior.Validation = $false
Assert-Failure { Invoke-PraRecovery @arguments } 'Validation echouee'
Assert-Equal $calls.Count 6
$calls.Clear()
$config.backup.offsiteLocation = ''
Assert-Failure { Invoke-PraRecovery @arguments -Simulate } 'offsite'
Assert-Equal $calls.Count 0
$config.backup.offsiteLocation = 'simulated-backup'
$config.validationTests[0].kind = 'unknown'
Assert-Failure { Invoke-PraRecovery @arguments } 'non supporte'
Assert-Equal $calls.Count 0
Write-Output 'PRA: 7 offline scenarios passed.'
