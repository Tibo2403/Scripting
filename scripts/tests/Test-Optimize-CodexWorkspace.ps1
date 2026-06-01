$ErrorActionPreference = 'Stop'
$doctor = Join-Path $PSScriptRoot '..\powershell\Optimize-CodexWorkspace.ps1'
$testRoot = Join-Path $env:TEMP 'codex-workspace-doctor-test'
$reportPath = Join-Path $testRoot 'report.json'
$agentsPath = Join-Path $testRoot 'AGENTS.md'

if (Test-Path -LiteralPath $testRoot) {
    Remove-Item -LiteralPath $testRoot -Recurse -Force
}

try {
    New-Item -ItemType Directory -Path (Join-Path $testRoot 'tests') -Force | Out-Null
    $fakeKey = 's' + 'k-test-workspace-doctor-not-real'
    Set-Content -LiteralPath (Join-Path $testRoot 'package.json') -Value '{"scripts":{"test":"node test.js","build":"node build.js"}}'
    Set-Content -LiteralPath (Join-Path $testRoot 'pyproject.toml') -Value '[tool.pytest.ini_options]'
    Set-Content -LiteralPath (Join-Path $testRoot '.env') -Value "OPENAI_API_KEY=$fakeKey"
    Set-Content -LiteralPath $agentsPath -Value "# Team guidance`n`nKeep this line."
    git -C $testRoot init | Out-Null

    & $doctor -ProjectPath $testRoot -Fix -ReportPath $reportPath
    & $doctor -ProjectPath $testRoot -Fix -ReportPath $reportPath

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
    if (-not $report.Git.IsRepository -or $report.Git.DirtyFileCount -eq 0) {
        throw 'Git repository changes were not reported.'
    }
    if ($report.Readiness.Score -ge 100) {
        throw 'Readiness score did not account for findings.'
    }
    if ('README.md' -notin $report.ContextFiles.Missing) {
        throw 'Missing README.md was not reported.'
    }
    if ((Get-Content -LiteralPath $reportPath -Raw) -match [regex]::Escape($fakeKey)) {
        throw 'A secret value leaked into the report.'
    }

    Write-Host 'Codex Workspace Doctor smoke test passed.'
}
finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
