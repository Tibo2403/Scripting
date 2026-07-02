[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$ConfigPath = ".\backup-config.json",

    [Parameter(Mandatory=$false)]
    [switch]$WhatIfMode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Log {
    param(
        [string]$Message,
        [ValidateSet("INFO","WARN","ERROR","OK")]
        [string]$Level = "INFO"
    )
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    $line | Tee-Object -FilePath $script:LogFile -Append
}

function Assert-Admin {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Le script doit être exécuté en tant qu'administrateur."
    }
}

function Test-PathOrThrow {
    param([string]$PathToTest, [string]$Label)
    if (-not (Test-Path $PathToTest)) {
        throw "$Label introuvable: $PathToTest"
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )
    Write-Log "Début étape: $Name" "INFO"
    try {
        if ($WhatIfMode) {
            Write-Log "WhatIf actif: étape simulée -> $Name" "WARN"
        } else {
            & $Action
        }
        Write-Log "Étape réussie: $Name" "OK"
    } catch {
        Write-Log "Étape échouée: $Name - $($_.Exception.Message)" "ERROR"
        throw
    }
}

function Test-TcpPort {
    param(
        [string]$HostName,
        [int]$Port
    )
    try {
        $r = Test-NetConnection -ComputerName $HostName -Port $Port -WarningAction SilentlyContinue
        return [bool]$r.TcpTestSucceeded
    } catch {
        return $false
    }
}

# --- Initialisation
Assert-Admin
Test-PathOrThrow -PathToTest $ConfigPath -Label "Fichier de configuration"

$config = Get-Content $ConfigPath -Raw | ConvertFrom-Json

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -Path $logDir -ItemType Directory | Out-Null }
$script:LogFile = Join-Path $logDir "PRA-$timestamp.log"

Write-Log "=== Démarrage PRA V2 ==="
Write-Log "Entreprise: $($config.company.name)"
Write-Log "Mode simulation: $($WhatIfMode.IsPresent)"

# --- Pré-checks
Invoke-Step -Name "Vérification connectivité dépôt backup primaire" -Action {
    if (-not (Test-Connection -ComputerName $config.backup.primaryRepositoryHost -Count 1 -Quiet)) {
        throw "Dépôt primaire injoignable: $($config.backup.primaryRepositoryHost)"
    }
}

Invoke-Step -Name "Vérification présence copie hors site" -Action {
    # Placeholder : remplacer par API/CLI outil backup
    if ([string]::IsNullOrWhiteSpace($config.backup.offsiteLocation)) {
        throw "Emplacement offsite non défini."
    }
}

# --- Restauration priorisée
foreach ($svc in $config.recoveryPriority | Sort-Object order) {
    Invoke-Step -Name "Restauration service [$($svc.name)] priorité $($svc.order)" -Action {
        Write-Log "Type: $($svc.type), RTO: $($svc.rto), RPO: $($svc.rpo)"
        # Placeholder restauration:
        # Exemple Veeam: Start-VBRRestoreVM / Start-VBRWindowsFileRestore ...
        # Exemple Windows Server Backup: wbadmin start recovery ...
        Start-Sleep -Seconds 2
    }
}

# --- Validation post-restauration
foreach ($test in $config.validationTests) {
    Invoke-Step -Name "Test $($test.name)" -Action {
        switch ($test.kind) {
            "tcp" {
                $ok = Test-TcpPort -HostName $test.host -Port $test.port
                if (-not $ok) { throw "Port KO: $($test.host):$($test.port)" }
            }
            "path" {
                if (-not (Test-Path $test.path)) { throw "Chemin introuvable: $($test.path)" }
            }
            default {
                throw "Type de test non supporté: $($test.kind)"
            }
        }
    }
}

Write-Log "=== PRA terminé avec succès ===" "OK"
Write-Log "Rapport: $script:LogFile"

# Code retour standard
exit 0
