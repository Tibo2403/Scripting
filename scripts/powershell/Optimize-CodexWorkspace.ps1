<#
.SYNOPSIS
    Audits a repository before launching Codex CLI.
.DESCRIPTION
    Detects the project stack, suggests validation commands, finds large files,
    scans common secret formats without printing values, audits Git readiness,
    and can maintain a generated section in AGENTS.md. No API key or dependency
    is required.
.PARAMETER ProjectPath
    Repository or project directory to inspect. Defaults to the current directory.
.PARAMETER Fix
    Creates or refreshes the managed Codex Workspace Doctor section in AGENTS.md.
.PARAMETER Disable
    Removes only the managed Codex Workspace Doctor section from AGENTS.md.
.PARAMETER ReportPath
    Optional path for a JSON report.
.PARAMETER ForceReportOverwrite
    Allows an existing JSON report to be replaced.
.PARAMETER MaxFileSizeMB
    Size threshold for files that should be reviewed before adding them to context.
.PARAMETER SecretScanMaxFileSizeMB
    Maximum size of individual text files inspected for possible secrets.
.PARAMETER LaunchCodex
    Starts Codex CLI in the inspected directory after the audit.
.PARAMETER Validate
    Runs the detected validation commands and calculates an efficiency metric.
.PARAMETER AllowProjectCommands
    Allows -Validate to execute project-defined tests and builds. Use only for
    repositories that you trust.
.PARAMETER ValidationTimeoutSeconds
    Maximum duration for each native validation command.
.PARAMETER ValidationLogLineLimit
    Maximum number of redacted standard output and error lines kept for failed
    or timed-out native validations.
.PARAMETER FailOn
    Optional CI policy. Returns a non-zero exit code for the selected conditions:
    Secret, ValidationFailure, or LowReadiness.
.PARAMETER MinimumReadinessScore
    Minimum acceptable readiness score when -FailOn LowReadiness is used.
.EXAMPLE
    PS> .\Optimize-CodexWorkspace.ps1 -ProjectPath C:\Projects\HealthApp
.EXAMPLE
    PS> .\Optimize-CodexWorkspace.ps1 -ProjectPath . -Fix -ReportPath .\codex-workspace-report.json
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Position = 0)]
    [string]$ProjectPath = (Get-Location).Path,
    [switch]$Fix,
    [switch]$Disable,
    [string]$ReportPath,
    [switch]$ForceReportOverwrite,
    [ValidateRange(1, 10240)]
    [int]$MaxFileSizeMB = 1,
    [ValidateRange(1, 10240)]
    [int]$SecretScanMaxFileSizeMB = 1,
    [switch]$Validate,
    [switch]$AllowProjectCommands,
    [ValidateRange(1, 86400)]
    [int]$ValidationTimeoutSeconds = 300,
    [ValidateRange(1, 200)]
    [int]$ValidationLogLineLimit = 20,
    [ValidateSet('Secret', 'ValidationFailure', 'LowReadiness')]
    [string[]]$FailOn = @(),
    [ValidateRange(0, 100)]
    [int]$MinimumReadinessScore = 80,
    [switch]$LaunchCodex
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Keep helpers in script scope: they share the audit parameters and ShouldProcess context.
. (Join-Path $PSScriptRoot 'workspace-doctor/Inventory.ps1')
. (Join-Path $PSScriptRoot 'workspace-doctor/Validation.ps1')
. (Join-Path $PSScriptRoot 'workspace-doctor/Readiness.ps1')
. (Join-Path $PSScriptRoot 'workspace-doctor/Agents.ps1')

$resolvedProject = Resolve-Path -LiteralPath $ProjectPath
if (-not (Test-Path -LiteralPath $resolvedProject.Path -PathType Container)) {
    throw "ProjectPath must be a directory: $ProjectPath"
}
$resolvedProject = [pscustomobject]@{
    Path = (Get-Item -LiteralPath $resolvedProject.Path).FullName
}
if ($Fix -and $Disable) {
    throw 'Use either -Fix or -Disable, not both.'
}
if ('ValidationFailure' -in $FailOn -and -not $Validate) {
    throw 'Use -Validate with -FailOn ValidationFailure.'
}

$inventory = Get-ProjectInventory
$allFiles = @($inventory.Files)
$largeFiles = @(
    $allFiles |
        Where-Object { $_.Length -gt ($MaxFileSizeMB * 1MB) } |
        Sort-Object -Property Length -Descending |
        ForEach-Object {
            [pscustomobject]@{
                Path = Get-RelativePath $resolvedProject.Path $_.FullName
                SizeMB = [math]::Round($_.Length / 1MB, 2)
            }
        }
)
$stacks = @(Get-DetectedStack $allFiles)
$validationCommands = @(Get-ValidationCommand $stacks)
$secretAudit = Get-SecretAudit $allFiles
$secretFindings = @($secretAudit.Findings)
$gitAudit = Get-GitAudit
$contextAudit = Get-ContextAudit
$agentsPath = Join-Path $resolvedProject.Path 'AGENTS.md'
$agentsStatus = if (Test-Path -LiteralPath $agentsPath) { 'present' } else { 'missing' }

if ($Fix) {
    $managedSection = Get-ManagedAgentsSection $stacks $validationCommands
    $agentsPath = Update-AgentsFile $managedSection
    $agentsStatus = 'updated'
    $contextAudit = Get-ContextAudit
}
elseif ($Disable) {
    $agentsPath = Disable-AgentsFile
    $agentsStatus = if (Test-Path -LiteralPath $agentsPath) { 'disabled-managed-section' } else { 'disabled' }
    $contextAudit = Get-ContextAudit
}
$readiness = Get-Readiness $gitAudit $contextAudit $largeFiles $secretFindings $secretAudit.SkippedLargeFiles $validationCommands
$validationResults = if ($Validate) {
    @(Invoke-ValidationCommand $validationCommands $AllowProjectCommands)
}
else {
    @()
}
$efficiency = Get-EfficiencyMetric $readiness $validationResults $Validate
$ciPolicy = Get-CiPolicy $FailOn $secretFindings $validationResults $readiness $MinimumReadinessScore

$report = [ordered]@{
    Timestamp = [DateTime]::UtcNow.ToString('o')
    Project = $resolvedProject.Path
    Stack = $stacks
    FilesInspected = $allFiles.Count
    ValidationCommands = $validationCommands
    ValidationPolicy = if ($AllowProjectCommands) { 'project-commands-enabled' } else { 'static-only' }
    ValidationTimeoutSeconds = $ValidationTimeoutSeconds
    ValidationLogLineLimit = $ValidationLogLineLimit
    ValidationResults = $validationResults
    Efficiency = $efficiency
    CI = $ciPolicy
    Readiness = $readiness
    Git = $gitAudit
    ContextFiles = $contextAudit
    AgentsFile = @{
        Path = $agentsPath
        Status = $agentsStatus
    }
    ContextReview = @{
        ExcludedDirectoriesPresent = $inventory.ExcludedPaths
        ExcludedDirectoryCount = $inventory.ExcludedPaths.Count
        ReparsePointsSkipped = $inventory.ReparsePointPaths
        ReparsePointCount = $inventory.ReparsePointPaths.Count
        LargeFiles = $largeFiles
        ThresholdMB = $MaxFileSizeMB
    }
    SecretScan = @{
        Status = if ($secretFindings.Count -gt 0) {
            'review-required'
        }
        elseif ($secretAudit.SkippedLargeFiles.Count -gt 0) {
            'partial'
        }
        else {
            'passed'
        }
        FilesScanned = $secretAudit.ScannedFileCount
        MaxFileSizeMB = $SecretScanMaxFileSizeMB
        SkippedLargeFiles = $secretAudit.SkippedLargeFiles
        SkippedLargeFileCount = $secretAudit.SkippedLargeFiles.Count
        Findings = $secretFindings
    }
}

Write-Information -InformationAction Continue 'Codex Workspace Doctor'
Write-Information -InformationAction Continue '----------------------'
Write-Information -InformationAction Continue "Project       : $($report.Project)"
Write-Information -InformationAction Continue "Stack         : $($stacks -join ', ')"
Write-Information -InformationAction Continue "Files checked : $($allFiles.Count)"
Write-Information -InformationAction Continue "Dirs excluded : $($inventory.ExcludedPaths.Count)"
Write-Information -InformationAction Continue "Links skipped : $($inventory.ReparsePointPaths.Count)"
Write-Information -InformationAction Continue "AGENTS.md     : $agentsStatus"
Write-Information -InformationAction Continue "Large files   : $($largeFiles.Count)"
Write-Information -InformationAction Continue "Secrets check : $($report.SecretScan.Status)"
Write-Information -InformationAction Continue "Secrets files : $($secretAudit.ScannedFileCount) scanned, $($secretAudit.SkippedLargeFiles.Count) skipped"
Write-Information -InformationAction Continue "Git status    : $(if ($gitAudit.IsRepository) { "$($gitAudit.Branch), $($gitAudit.DirtyFileCount) change(s)" } elseif ($gitAudit.Available) { 'not a repository' } else { 'git unavailable' })"
Write-Information -InformationAction Continue "Readiness     : $($readiness.Score)/100"
Write-Information -InformationAction Continue "Efficiency    : $(if ($null -ne $efficiency.Score) { "$($efficiency.Score)/100" } else { $efficiency.Status })"
Write-Information -InformationAction Continue "CI policy     : $($ciPolicy.Status)"
Write-Information -InformationAction Continue ''
Write-Information -InformationAction Continue 'Recommended validation commands:'
foreach ($command in $validationCommands) {
    Write-Information -InformationAction Continue "  $command"
}
if ($Validate) {
    Write-Information -InformationAction Continue ''
    Write-Information -InformationAction Continue 'Validation results:'
    foreach ($validationResult in $validationResults) {
        $reason = if ($validationResult.Reason) { " - $($validationResult.Reason)" } else { '' }
        Write-Information -InformationAction Continue "  $($validationResult.Status): $($validationResult.Command) ($($validationResult.DurationSeconds)s)$reason"
        foreach ($line in @($validationResult.StdOutTail) + @($validationResult.StdErrTail)) {
            Write-Information -InformationAction Continue "    $line"
        }
    }
}
Write-Information -InformationAction Continue ''
Write-Information -InformationAction Continue 'Recommendations:'
foreach ($recommendation in $readiness.Recommendations) {
    Write-Information -InformationAction Continue "  - $recommendation"
}
if ($secretFindings.Count -gt 0) {
    Write-Warning "Review $($secretFindings.Count) possible secret finding(s). Values were intentionally hidden."
    $secretFindings | Format-Table -AutoSize
}
if ($secretAudit.SkippedLargeFiles.Count -gt 0) {
    Write-Warning "Review $($secretAudit.SkippedLargeFiles.Count) text file(s) skipped by the secret scan size limit."
}

if ($ReportPath) {
    if (Test-Path -LiteralPath $ReportPath -PathType Container) {
        throw "ReportPath must be a file path: $ReportPath"
    }
    if ((Test-Path -LiteralPath $ReportPath) -and -not $ForceReportOverwrite) {
        throw "Report already exists. Use -ForceReportOverwrite to replace it: $ReportPath"
    }
    $reportDirectory = Split-Path -Parent $ReportPath
    if ($reportDirectory -and -not (Test-Path -LiteralPath $reportDirectory)) {
        New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
    }
    if ($PSCmdlet.ShouldProcess($ReportPath, 'Write workspace doctor JSON report')) {
        $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding utf8
        Write-Information -InformationAction Continue "Report saved  : $ReportPath"
    }
}

if ($ciPolicy.Status -eq 'failed') {
    foreach ($failure in $ciPolicy.Failures) {
        Write-Warning "CI policy failure: $failure"
    }
    exit 1
}

if ($LaunchCodex) {
    $codex = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $codex) {
        throw 'Codex CLI was not found in PATH.'
    }
    Push-Location $resolvedProject.Path
    try {
        & $codex.Source
    }
    finally {
        Pop-Location
    }
}
