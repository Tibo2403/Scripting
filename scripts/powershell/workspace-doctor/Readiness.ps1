# Private helpers loaded in Optimize-CodexWorkspace.ps1 script scope.

function Get-EfficiencyMetric {
    param(
        [hashtable]$Readiness,
        [object[]]$ValidationResults,
        [bool]$ValidateRequested
    )

    if (-not $ValidateRequested) {
        return [ordered]@{
            Status = 'not-measured'
            Score = $null
            ValidationPassRate = $null
            DurationSeconds = 0
            Explanation = 'Run with -Validate to measure efficiency using detected project checks.'
        }
    }

    $executed = @($ValidationResults | Where-Object { $_.Status -in @('passed', 'failed', 'timed-out') })
    $duration = ($ValidationResults | Measure-Object -Property DurationSeconds -Sum).Sum
    if ($executed.Count -eq 0) {
        return [ordered]@{
            Status = 'unavailable'
            Score = $null
            ValidationPassRate = $null
            DurationSeconds = [math]::Round($duration, 3)
            Explanation = 'No detected validation command could be executed on this machine.'
        }
    }

    $passed = @($executed | Where-Object { $_.Status -eq 'passed' }).Count
    $passRate = [math]::Round(($passed / $executed.Count) * 100, 2)
    $score = [math]::Round(($Readiness.Score * 0.5) + ($passRate * 0.5), 2)
    return [ordered]@{
        Status = 'measured'
        Score = $score
        ValidationPassRate = $passRate
        DurationSeconds = [math]::Round($duration, 3)
        Explanation = 'Score = 50% workspace readiness + 50% successful executable validations.'
    }
}

function Get-CiPolicy {
    param(
        [string[]]$Conditions,
        [object[]]$SecretFindings,
        [object[]]$ValidationResults,
        [hashtable]$Readiness,
        [int]$MinimumReadinessScore
    )

    $failures = [System.Collections.Generic.List[string]]::new()
    if ('Secret' -in $Conditions -and $SecretFindings.Count -gt 0) {
        $failures.Add("Secret scan requires review: $($SecretFindings.Count) finding(s).")
    }
    if ('ValidationFailure' -in $Conditions) {
        $failedValidations = @($ValidationResults | Where-Object { $_.Status -in @('failed', 'timed-out') })
        if ($failedValidations.Count -gt 0) {
            $failures.Add("Validation failed or timed out: $($failedValidations.Count) command(s).")
        }
    }
    if ('LowReadiness' -in $Conditions -and $Readiness.Score -lt $MinimumReadinessScore) {
        $failures.Add("Readiness score $($Readiness.Score) is below the required $MinimumReadinessScore.")
    }

    return [ordered]@{
        Status = if ($Conditions.Count -eq 0) { 'disabled' } elseif ($failures.Count -gt 0) { 'failed' } else { 'passed' }
        FailOn = @($Conditions)
        MinimumReadinessScore = $MinimumReadinessScore
        Failures = @($failures)
    }
}

function Invoke-Git {
    param(
        [string[]]$Arguments
    )

    $output = & git -c "safe.directory=$($resolvedProject.Path)" -C $resolvedProject.Path @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return @($output)
}

function Get-GitAudit {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        return [ordered]@{
            Available = $false
            IsRepository = $false
            Branch = $null
            DirtyFiles = @()
            DirtyFileCount = 0
            UntrackedFileCount = 0
        }
    }

    $insideWorkTree = @(Invoke-Git -Arguments @('rev-parse', '--is-inside-work-tree'))
    if ($insideWorkTree.Count -eq 0 -or $insideWorkTree[0] -ne 'true') {
        return [ordered]@{
            Available = $true
            IsRepository = $false
            Branch = $null
            DirtyFiles = @()
            DirtyFileCount = 0
            UntrackedFileCount = 0
        }
    }

    $branch = @(Invoke-Git -Arguments @('branch', '--show-current'))
    $dirtyFiles = @(Invoke-Git -Arguments @('status', '--porcelain'))
    $untrackedFileCount = @($dirtyFiles | Where-Object { $_ -match '^\?\?' }).Count
    return [ordered]@{
        Available = $true
        IsRepository = $true
        Branch = if ($branch) { $branch[0] } else { '(detached HEAD)' }
        DirtyFiles = $dirtyFiles
        DirtyFileCount = $dirtyFiles.Count
        UntrackedFileCount = $untrackedFileCount
    }
}

function Get-ContextAudit {
    $recommendedFiles = @('README.md', 'AGENTS.md', '.gitignore')
    $present = [System.Collections.Generic.List[string]]::new()
    $missing = [System.Collections.Generic.List[string]]::new()
    foreach ($file in $recommendedFiles) {
        if (Test-ProjectFile $file) {
            $present.Add($file)
        }
        else {
            $missing.Add($file)
        }
    }
    return [ordered]@{
        Present = @($present)
        Missing = @($missing)
    }
}

function Get-Readiness {
    param(
        [hashtable]$GitAudit,
        [hashtable]$ContextAudit,
        [object[]]$LargeFiles,
        [object[]]$SecretFindings,
        [object[]]$SecretScanSkippedLargeFiles,
        [string[]]$Commands
    )

    $score = 100
    $recommendations = [System.Collections.Generic.List[string]]::new()
    if ('AGENTS.md' -in $ContextAudit.Missing) {
        $score -= 15
        Add-UniqueValue $recommendations 'Run with -Fix to generate the managed AGENTS.md guidance.'
    }
    if ('README.md' -in $ContextAudit.Missing) {
        $score -= 10
        Add-UniqueValue $recommendations 'Add a README.md so Codex can understand the project quickly.'
    }
    if ('.gitignore' -in $ContextAudit.Missing) {
        $score -= 5
        Add-UniqueValue $recommendations 'Add a .gitignore for local and generated files.'
    }
    if ($SecretFindings.Count -gt 0) {
        $score -= 30
        Add-UniqueValue $recommendations 'Review possible secrets before sharing context or committing changes.'
    }
    if ($SecretScanSkippedLargeFiles.Count -gt 0) {
        $score -= 5
        Add-UniqueValue $recommendations 'Review text files skipped by the secret scan size limit.'
    }
    if ($LargeFiles.Count -gt 0) {
        $score -= 10
        Add-UniqueValue $recommendations 'Review large files before adding them to the Codex context.'
    }
    if (-not $GitAudit.Available) {
        $score -= 5
        Add-UniqueValue $recommendations 'Install Git to include repository readiness checks.'
    }
    elseif (-not $GitAudit.IsRepository) {
        $score -= 10
        Add-UniqueValue $recommendations 'Initialize Git so changes can be reviewed before and after a Codex session.'
    }
    elseif ($GitAudit.DirtyFileCount -gt 0) {
        $score -= 10
        Add-UniqueValue $recommendations 'Review existing Git changes before starting a broad Codex task.'
    }
    if ('Add the project validation command to AGENTS.md' -in $Commands) {
        $score -= 10
        Add-UniqueValue $recommendations 'Document at least one project validation command.'
    }
    if ($score -lt 0) {
        $score = 0
    }
    if ($recommendations.Count -eq 0) {
        $recommendations.Add('Workspace is ready for a focused Codex session.')
    }
    return [ordered]@{
        Score = $score
        Recommendations = @($recommendations)
    }
}
