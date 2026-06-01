$ErrorActionPreference = 'Stop'
$doctor = Join-Path $PSScriptRoot '..\powershell\Optimize-CodexWorkspace.ps1'
$testRoot = Join-Path $env:TEMP 'codex-workspace-doctor-test'
$reportPath = Join-Path $testRoot 'report.json'
$trustedReportPath = Join-Path $testRoot 'trusted-report.json'
$agentsPath = Join-Path $testRoot 'AGENTS.md'

if (Test-Path -LiteralPath $testRoot) {
    Remove-Item -LiteralPath $testRoot -Recurse -Force
}

try {
    New-Item -ItemType Directory -Path (Join-Path $testRoot 'tests') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $testRoot 'frontend\node_modules\sample') -Force | Out-Null
    $fakeKey = 's' + 'k-test-workspace-doctor-not-real'
    $excludedFakeKey = 's' + 'k-excluded-workspace-doctor-not-real'
    Set-Content -LiteralPath (Join-Path $testRoot 'package.json') -Value '{"scripts":{"test":"node test.js","build":"node build.js"}}'
    Set-Content -LiteralPath (Join-Path $testRoot 'pyproject.toml') -Value '[tool.pytest.ini_options]'
    Set-Content -LiteralPath (Join-Path $testRoot '.env') -Value "OPENAI_API_KEY=$fakeKey"
    Set-Content -LiteralPath (Join-Path $testRoot 'frontend\node_modules\sample\.env') -Value "OPENAI_API_KEY=$excludedFakeKey"
    Set-Content -LiteralPath $agentsPath -Value "# Team guidance`n`nKeep this line."
    git -C $testRoot init | Out-Null

    & $doctor -ProjectPath $testRoot -Fix -ReportPath $reportPath
    $overwriteRefused = $false
    try {
        & $doctor -ProjectPath $testRoot -ReportPath $reportPath
    }
    catch {
        $overwriteRefused = $_.Exception.Message -match 'Report already exists'
    }
    if (-not $overwriteRefused) {
        throw 'Existing reports can be overwritten without explicit opt-in.'
    }
    & $doctor -ProjectPath $testRoot -Fix -Validate -ReportPath $reportPath -ForceReportOverwrite

    $agents = Get-Content -LiteralPath $agentsPath -Raw
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    $markerCount = ([regex]::Matches($agents, '<!-- BEGIN CODEX WORKSPACE DOCTOR -->')).Count

    if ($markerCount -ne 1) {
        throw 'The managed AGENTS.md block was duplicated.'
    }
    if ($agents -notmatch 'Keep this line') {
        throw 'Existing AGENTS.md guidance was not preserved.'
    }
    if ('Python' -notin $report.Stack -or 'JavaScript' -notin $report.Stack) {
        throw 'Expected stacks were not detected.'
    }
    if ('npm run test' -notin $report.ValidationCommands -or 'python -m pytest' -notin $report.ValidationCommands) {
        throw 'Expected validation commands were not detected.'
    }
    if ($report.SecretScan.Status -ne 'review-required') {
        throw 'The fake API key was not reported.'
    }
    if ($report.SecretScan.Findings.Count -ne 1) {
        throw 'Files in excluded directories were scanned for secrets.'
    }
    if ('frontend\node_modules' -notin $report.ContextReview.ExcludedDirectoriesPresent) {
        throw 'Nested excluded directories were not reported.'
    }
    if ($report.ContextReview.ExcludedDirectoryCount -ne $report.ContextReview.ExcludedDirectoriesPresent.Count) {
        throw 'The excluded directory count is incorrect.'
    }
    if (-not $report.Git.IsRepository -or $report.Git.DirtyFileCount -eq 0) {
        throw 'Git repository changes were not reported.'
    }
    if ($report.Readiness.Score -ge 100) {
        throw 'Readiness score did not account for findings.'
    }
    if ($report.Efficiency.Status -eq 'not-measured' -or $report.ValidationResults.Count -eq 0) {
        throw 'Efficiency metric was not calculated from validation results.'
    }
    $npmValidation = @($report.ValidationResults | Where-Object { $_.Command -eq 'npm run test' })
    if ($npmValidation.Count -ne 1 -or $npmValidation[0].Status -ne 'skipped') {
        throw 'Project-defined validation commands ran without explicit opt-in.'
    }
    if ('README.md' -notin $report.ContextFiles.Missing) {
        throw 'Missing README.md was not reported.'
    }
    if ((Get-Content -LiteralPath $reportPath -Raw) -match [regex]::Escape($fakeKey)) {
        throw 'A secret value leaked into the report.'
    }
    if ((Get-Content -LiteralPath $reportPath -Raw) -match [regex]::Escape($excludedFakeKey)) {
        throw 'A secret value from an excluded directory leaked into the report.'
    }

    & $doctor -ProjectPath $testRoot -Validate -AllowProjectCommands -ReportPath $trustedReportPath
    $trustedReport = Get-Content -LiteralPath $trustedReportPath -Raw | ConvertFrom-Json
    $trustedNpmValidation = @($trustedReport.ValidationResults | Where-Object { $_.Command -eq 'npm run test' })
    if ($trustedNpmValidation.Count -ne 1 -or $trustedNpmValidation[0].Status -eq 'skipped') {
        throw 'Trusted project validation commands did not run after explicit opt-in.'
    }

    & $doctor -ProjectPath $testRoot -Disable
    $disabledAgents = Get-Content -LiteralPath $agentsPath -Raw
    if ($disabledAgents -match '<!-- BEGIN CODEX WORKSPACE DOCTOR -->') {
        throw 'The managed AGENTS.md block was not removed.'
    }
    if ($disabledAgents -notmatch 'Keep this line') {
        throw 'Disabling removed human AGENTS.md guidance.'
    }

    $generatedOnlyRoot = Join-Path $testRoot 'generated-only'
    New-Item -ItemType Directory -Path $generatedOnlyRoot -Force | Out-Null
    & $doctor -ProjectPath $generatedOnlyRoot -Fix
    & $doctor -ProjectPath $generatedOnlyRoot -Disable
    if (Test-Path -LiteralPath (Join-Path $generatedOnlyRoot 'AGENTS.md')) {
        throw 'Generated-only AGENTS.md was not removed when disabled.'
    }

    Write-Host 'Codex Workspace Doctor smoke test passed.'
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
