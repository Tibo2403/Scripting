# Orchestration shared by the operational entry point and offline scenario tests.
function Invoke-PraRecovery {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$Configuration,
        [Parameter(Mandatory)][scriptblock]$RestoreService,
        [Parameter(Mandatory)][scriptblock]$TestRepository,
        [Parameter(Mandatory)][scriptblock]$TestValidation,
        [Parameter(Mandatory)][scriptblock]$Log,
        [switch]$Simulate
    )
    $ErrorActionPreference = 'Stop'
    if ([string]::IsNullOrWhiteSpace($Configuration.backup.primaryRepositoryHost)) {
        throw 'Depot primaire non defini.'
    }
    if ([string]::IsNullOrWhiteSpace($Configuration.backup.offsiteLocation)) {
        throw 'Emplacement offsite non defini.'
    }
    $services = @($Configuration.recoveryPriority | Sort-Object order)
    if ($services.Count -eq 0) { throw 'Aucun service a restaurer.' }
    foreach ($service in $services) {
        if ([string]::IsNullOrWhiteSpace($service.name)) { throw 'Nom de service manquant.' }
    }
    foreach ($test in $Configuration.validationTests) {
        if ($test.kind -notin @('tcp', 'path')) { throw "Type de test non supporte: $($test.kind)" }
    }
    try {
        if (-not $Simulate -and -not (& $TestRepository $Configuration.backup.primaryRepositoryHost)) {
            throw 'Depot primaire injoignable.'
        }
        foreach ($service in $services) {
            & $Log "Restauration service [$($service.name)] priorite $($service.order)"
            if (-not $Simulate) { & $RestoreService $service }
        }
        foreach ($test in $Configuration.validationTests) {
            & $Log "Validation [$($test.name)]"
            if (-not $Simulate -and -not (& $TestValidation $test)) {
                throw "Validation echouee: $($test.name)"
            }
        }
        & $Log $(if ($Simulate) { 'Simulation terminee : aucune restauration effectuee.' } else { 'PRA termine avec succes.' })
    } catch {
        & $Log "PRA echoue: $($_.Exception.Message)"
        throw
    }
}
