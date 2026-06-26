$ErrorActionPreference = 'Stop'
$doctor = Join-Path $PSScriptRoot '..\powershell\Optimize-CodexWorkspace.ps1'
$testRoot = Join-Path $env:TEMP 'codex-workspace-doctor-test'
$reportPath = Join-Path $testRoot 'report.json'
$trustedReportPath = Join-Path $testRoot 'trusted-report.json'
$ciReportPath = Join-Path $testRoot 'ci-report.json'
$partialReportPath = Join-Path $testRoot 'partial-report.json'
$agentsPath = Join-Path $testRoot 'AGENTS.md'

if (Test-Path -LiteralPath $testRoot) {
    Remove-Item -LiteralPath $testRoot -Recurse -Force
}

try {
    New-Item -ItemType Directory -Path (Join-Path $testRoot 'tests') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $testRoot 'frontend\node_modules\sample') -Force | Out-Null
    $fakeKey = 's' + 'k-test-workspace-doctor-not-real'
    $excludedFakeKey = 's' + 'k-excluded-workspace-doctor-not-real'
    $fakeAwsKey = 'AK' + 'IA1234567890ABCDEF'
    $validationLogSecret = 'validation-log-secret-value'
    Set-Content -LiteralPath (Join-Path $testRoot 'package.json') -Value '{"scripts":{"test":"node test.js","lint":"node slow.js","build":"node build.js"}}'
    Set-Content -LiteralPath (Join-Path $testRoot 'test.js') -Value "console.error('to' + 'ken=' + '$validationLogSecret'); process.exit(1);"
    Set-Content -LiteralPath (Join-Path $testRoot 'slow.js') -Value "setTimeout(() => {}, 30000);"
    Set-Content -LiteralPath (Join-Path $testRoot 'pyproject.toml') -Value '[tool.pytest.ini_options]'
    Set-Content -LiteralPath (Join-Path $testRoot '.env') -Value "OPENAI_API_KEY=$fakeKey"
    Set-Content -LiteralPath (Join-Path $testRoot 'tokens.txt') -Value $fakeAwsKey
    Set-Content -LiteralPath (Join-Path $testRoot 'large.env') -Value ('x' * 2MB)
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
    if ($report.SecretScan.Findings.Count -ne 2) {
        throw 'Files in excluded directories were scanned for secrets.'
    }
    if ('.env' -notin $report.SecretScan.Findings.Path) {
        throw 'Secret finding paths were not reported relative to the project root.'
    }
    if ('AWS access key' -notin $report.SecretScan.Findings.Type) {
        throw 'AWS access keys were not detected.'
    }
    if ($report.SecretScan.SkippedLargeFileCount -ne 1 -or 'large.env' -notin $report.SecretScan.SkippedLargeFiles.Path) {
        throw 'Large text files skipped by the secret scan were not reported.'
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

    & $doctor -ProjectPath $testRoot -Validate -AllowProjectCommands -ValidationTimeoutSeconds 15 -ValidationLogLineLimit 2 -ReportPath $trustedReportPath
    $trustedReport = Get-Content -LiteralPath $trustedReportPath -Raw | ConvertFrom-Json
    $trustedNpmValidation = @($trustedReport.ValidationResults | Where-Object { $_.Command -eq 'npm run test' })
    if ($trustedNpmValidation.Count -ne 1 -or $trustedNpmValidation[0].Status -eq 'skipped') {
        throw 'Trusted project validation commands did not run after explicit opt-in.'
    }
    $trustedNpmOutputTail = @($trustedNpmValidation[0].StdOutTail) + @($trustedNpmValidation[0].StdErrTail)
    if ($trustedNpmValidation[0].Status -ne 'failed' -or ($trustedNpmOutputTail -join "`n") -notmatch '\[REDACTED\]') {
        $safeStdOut = (@($trustedNpmValidation[0].StdOutTail) -join ' | ') -replace [regex]::Escape($validationLogSecret), '[UNREDACTED-TEST-SECRET]'
        $safeStdErr = (@($trustedNpmValidation[0].StdErrTail) -join ' | ') -replace [regex]::Escape($validationLogSecret), '[UNREDACTED-TEST-SECRET]'
        throw "Failed validation diagnostics were not captured and redacted. Status=$($trustedNpmValidation[0].Status); StdOutTail=$safeStdOut; StdErrTail=$safeStdErr"
    }
    if ((Get-Content -LiteralPath $trustedReportPath -Raw) -match [regex]::Escape($validationLogSecret)) {
        throw 'A secret value leaked from validation diagnostics into the report.'
    }
    $trustedNpmLint = @($trustedReport.ValidationResults | Where-Object { $_.Command -eq 'npm run lint' })
    if ($trustedNpmLint.Count -ne 1 -or $trustedNpmLint[0].Status -ne 'timed-out') {
        throw 'Native validation commands did not stop after the configured timeout.'
    }
    if ($trustedReport.ValidationTimeoutSeconds -ne 15 -or $trustedReport.ValidationLogLineLimit -ne 2) {
        throw 'Validation timeout and log limits were not written to the report.'
    }

    $powerShellPath = (Get-Process -Id $PID).Path
    $ciStdOutPath = Join-Path $testRoot 'ci-policy.stdout.log'
    $ciStdErrPath = Join-Path $testRoot 'ci-policy.stderr.log'
    $ciProcess = Start-Process -FilePath $powerShellPath -ArgumentList @(
        '-NoProfile',
        '-File', $doctor,
        '-ProjectPath', $testRoot,
        '-FailOn', 'Secret',
        '-ReportPath', $ciReportPath
    ) -NoNewWindow -Wait -PassThru -RedirectStandardOutput $ciStdOutPath -RedirectStandardError $ciStdErrPath
    if ($ciProcess.ExitCode -ne 1) {
        throw 'CI secret policy did not return a non-zero exit code.'
    }
    $ciReport = Get-Content -LiteralPath $ciReportPath -Raw | ConvertFrom-Json
    if ($ciReport.CI.Status -ne 'failed' -or 'Secret' -notin $ciReport.CI.FailOn) {
        throw 'CI secret policy failure was not written to the report.'
    }
    if ($ciReport.SecretScan.Findings.Count -ne 2) {
        throw 'Redacted validation diagnostics were reported as new secrets.'
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

    $partialRoot = Join-Path $testRoot 'partial-secret-scan'
    New-Item -ItemType Directory -Path $partialRoot -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $partialRoot 'large.env') -Value ('x' * 2MB)
    & $doctor -ProjectPath $partialRoot -ReportPath $partialReportPath
    $partialReport = Get-Content -LiteralPath $partialReportPath -Raw | ConvertFrom-Json
    if ($partialReport.SecretScan.Status -ne 'partial' -or $partialReport.SecretScan.SkippedLargeFileCount -ne 1) {
        throw 'Partial secret scan coverage was not reported.'
    }

    Write-Host 'Codex Workspace Doctor smoke test passed.'
}
catch {
    $message = $_.Exception.Message -replace '\r?\n', ' '
    if ($env:GITHUB_ACTIONS -eq 'true') {
        Write-Output "::error title=Codex Workspace Doctor smoke test::$message"
    }
    throw
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
