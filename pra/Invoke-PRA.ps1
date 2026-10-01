[CmdletBinding()]
param(
    [string]$ConfigPath = '.\backup-config.json',
    [switch]$WhatIfMode,
    [scriptblock]$RestoreAction,
    [string]$LogDirectory = (Join-Path $PSScriptRoot 'logs')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Recovery.ps1')
if (-not $WhatIfMode -and -not $RestoreAction) {
    throw 'Restauration indisponible : fournir -RestoreAction avec un connecteur de sauvegarde valide.'
}
if (-not $WhatIfMode) {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($currentUser)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'La restauration doit etre executee en tant qu administrateur.'
    }
}
$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$null = New-Item -Path $LogDirectory -ItemType Directory -Force
$logFile = Join-Path $LogDirectory "PRA-$(Get-Date -Format 'yyyyMMdd-HHmmss-fff').log"
$arguments = @{
    Configuration = $config
    Simulate = $WhatIfMode
    RestoreService = { param($Service) & $RestoreAction $Service }
    TestRepository = {
        param($RepositoryHost)
        Test-Connection -ComputerName $RepositoryHost -Count 1 -Quiet
    }
    TestValidation = {
        param($Test)
        switch ($Test.kind) {
            'tcp' {
                $result = Test-NetConnection -ComputerName $Test.host -Port $Test.port -WarningAction SilentlyContinue
                [bool]$result.TcpTestSucceeded
            }
            'path' { Test-Path -LiteralPath $Test.path }
            default { throw "Type de test non supporte: $($Test.kind)" }
        }
    }
    Log = {
        param($Message)
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message" | Tee-Object -FilePath $logFile -Append
    }
}
Invoke-PraRecovery @arguments
Write-Output "Rapport: $logFile"
