<#
.SYNOPSIS
    Audits a repository before launching Codex CLI.
.DESCRIPTION
    Detects the project stack, suggests validation commands, finds large files,
    scans common secret formats without printing values, and can maintain a
    generated section in AGENTS.md. No API key or dependency is required.
.PARAMETER ProjectPath
    Repository or project directory to inspect. Defaults to the current directory.
.PARAMETER Fix
    Creates or refreshes the managed Codex Workspace Doctor section in AGENTS.md.
.PARAMETER ReportPath
    Optional path for a JSON report.
.PARAMETER MaxFileSizeMB
    Size threshold for files that should be reviewed before adding them to context.
.PARAMETER LaunchCodex
    Starts Codex CLI in the inspected directory after the audit.
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
    [string]$ReportPath,
    [ValidateRange(1, 10240)]
    [int]$MaxFileSizeMB = 1,
    [switch]$LaunchCodex
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$beginMarker = '<!-- BEGIN CODEX WORKSPACE DOCTOR -->'
$endMarker = '<!-- END CODEX WORKSPACE DOCTOR -->'
$excludedDirectories = @(
    '.git', '.idea', '.next', '.pytest_cache', '.tox', '.venv', '.vscode',
    '__pycache__', 'bin', 'build', 'coverage', 'dist', 'node_modules', 'obj',
    'target', 'venv'
)
$textExtensions = @(
    '.bash', '.cfg', '.conf', '.cs', '.css', '.env', '.go', '.gradle', '.html',
    '.ini', '.java', '.js', '.json', '.jsx', '.md', '.php', '.ps1', '.psd1',
    '.psm1', '.py', '.rb', '.rs', '.sh', '.sql', '.toml', '.ts', '.tsx',
    '.txt', '.xml', '.yaml', '.yml'
)
$textNames = @(
    '.env', '.gitignore', 'Dockerfile', 'Gemfile', 'Makefile', 'package-lock.json'
)

function Get-RelativePath {
    param(
        [string]$Root,
        [string]$Path
    )

    return $Path.Substring($Root.Length).TrimStart('\', '/')
}

function Test-IsExcluded {
    param(
        [string]$RelativePath
    )

    $segments = $RelativePath -split '[\\/]'
    foreach ($segment in $segments) {
        if ($segment -in $excludedDirectories) {
            return $true
        }
    }
    return $false
}

function Add-UniqueValue {
    param(
        [System.Collections.Generic.List[string]]$List,
        [string]$Value
    )

    if ($Value -and -not $List.Contains($Value)) {
        $List.Add($Value)
    }
}

function Test-ProjectFile {
    param(
        [string]$Name
    )

    return Test-Path -LiteralPath (Join-Path $resolvedProject.Path $Name)
}

function Get-DetectedStacks {
    param(
        [System.IO.FileInfo[]]$Files
    )

    $stacks = [System.Collections.Generic.List[string]]::new()
    $extensions = @($Files | Select-Object -ExpandProperty Extension -Unique)

    if ((Test-ProjectFile 'pyproject.toml') -or (Test-ProjectFile 'requirements.txt') -or '.py' -in $extensions) {
        Add-UniqueValue $stacks 'Python'
    }
    if ((Test-ProjectFile 'package.json') -or '.js' -in $extensions -or '.jsx' -in $extensions) {
        Add-UniqueValue $stacks 'JavaScript'
    }
    if ((Test-ProjectFile 'tsconfig.json') -or '.ts' -in $extensions -or '.tsx' -in $extensions) {
        Add-UniqueValue $stacks 'TypeScript'
    }
    if ((Test-ProjectFile 'Dockerfile') -or (Test-ProjectFile 'docker-compose.yml') -or (Test-ProjectFile 'compose.yaml')) {
        Add-UniqueValue $stacks 'Docker'
    }
    if ((Test-ProjectFile 'go.mod') -or '.go' -in $extensions) {
        Add-UniqueValue $stacks 'Go'
    }
    if ((Test-ProjectFile 'Cargo.toml') -or '.rs' -in $extensions) {
        Add-UniqueValue $stacks 'Rust'
    }
    if (@($Files | Where-Object { $_.Extension -eq '.csproj' }).Count -gt 0) {
        Add-UniqueValue $stacks '.NET'
    }
    if ((Test-ProjectFile 'pom.xml') -or (Test-ProjectFile 'build.gradle') -or '.java' -in $extensions) {
        Add-UniqueValue $stacks 'Java'
    }
    if (@($Files | Where-Object { $_.Name -eq '__manifest__.py' }).Count -gt 0) {
        Add-UniqueValue $stacks 'Odoo'
    }
    if ('.ps1' -in $extensions -or '.psm1' -in $extensions) {
        Add-UniqueValue $stacks 'PowerShell'
    }

    if ($stacks.Count -eq 0) {
        $stacks.Add('Generic')
    }
    return @($stacks)
}

function Get-ValidationCommands {
    param(
        [string[]]$Stacks
    )

    $commands = [System.Collections.Generic.List[string]]::new()
    if ('Python' -in $Stacks) {
        if ((Test-ProjectFile 'pytest.ini') -or (Test-ProjectFile 'pyproject.toml') -or (Test-Path -LiteralPath (Join-Path $resolvedProject.Path 'tests'))) {
            Add-UniqueValue $commands 'python -m pytest'
        }
        Add-UniqueValue $commands 'python -m compileall .'
    }

    if (Test-ProjectFile 'package.json') {
        try {
            $package = Get-Content -LiteralPath (Join-Path $resolvedProject.Path 'package.json') -Raw | ConvertFrom-Json
            if ($package.scripts) {
                foreach ($scriptName in @('test', 'lint', 'build')) {
                    if ($package.scripts.PSObject.Properties.Name -contains $scriptName) {
                        Add-UniqueValue $commands "npm run $scriptName"
                    }
                }
            }
        }
        catch {
            Add-UniqueValue $commands 'Review package.json: invalid JSON'
        }
    }
    if ('PowerShell' -in $Stacks) {
        Add-UniqueValue $commands 'Invoke-ScriptAnalyzer -Path . -Recurse'
    }
    if ('Go' -in $Stacks) {
        Add-UniqueValue $commands 'go test ./...'
    }
    if ('Rust' -in $Stacks) {
        Add-UniqueValue $commands 'cargo test'
    }
    if ('.NET' -in $Stacks) {
        Add-UniqueValue $commands 'dotnet test'
    }
    if ('Java' -in $Stacks) {
        if (Test-ProjectFile 'pom.xml') {
            Add-UniqueValue $commands 'mvn test'
        }
        elseif (Test-ProjectFile 'gradlew') {
            Add-UniqueValue $commands '.\gradlew test'
        }
    }
    if ($commands.Count -eq 0) {
        $commands.Add('Add the project validation command to AGENTS.md')
    }
    return @($commands)
}

function Get-SecretFindings {
    param(
        [System.IO.FileInfo[]]$Files
    )

    $openAiPattern = 's' + 'k-[A-Za-z0-9_-]{20,}'
    $githubPattern = 'gh' + '[pousr]_[A-Za-z0-9]{20,}'
    $assignedPattern = '(?i)\b(password|passwd|api[_-]?key|token|secret)\b\s*[:=]\s*["'']?([^\s"'']{8,})'
    $privateKeyPattern = '-----BEGIN ([A-Z ]+ )?PRIVATE KEY-----'
    $patterns = @(
        @{ Name = 'OpenAI-style API key'; Pattern = $openAiPattern },
        @{ Name = 'GitHub token'; Pattern = $githubPattern },
        @{ Name = 'Assigned secret'; Pattern = $assignedPattern },
        @{ Name = 'Private key'; Pattern = $privateKeyPattern }
    )
    $findings = [System.Collections.Generic.List[object]]::new()

    foreach ($file in $Files) {
        if ($file.Length -gt 1MB) {
            continue
        }
        if ($file.Extension -notin $textExtensions -and $file.Name -notin $textNames) {
            continue
        }

        $lineNumber = 0
        foreach ($line in Get-Content -LiteralPath $file.FullName -ErrorAction SilentlyContinue) {
            $lineNumber++
            foreach ($pattern in $patterns) {
                if ($line -match $pattern.Pattern) {
                    if ($pattern.Name -eq 'Assigned secret') {
                        $assignedValue = $Matches[2]
                        if ($assignedValue -match '^(\$|os\.environ/|process\.env|Read-Host|<|\$\{)') {
                            continue
                        }
                    }
                    $findings.Add([pscustomobject]@{
                        Type = $pattern.Name
                        Path = Get-RelativePath $resolvedProject.Path $file.FullName
                        Line = $lineNumber
                    })
                    break
                }
            }
        }
    }
    return @($findings)
}

function Get-ManagedAgentsSection {
    param(
        [string[]]$Stacks,
        [string[]]$Commands
    )

    $stackText = $Stacks -join ', '
    $commandLines = @($Commands | ForEach-Object { "- ``$_``" }) -join "`n"
    return @"
$beginMarker
## Codex Workspace Doctor

This section is generated by `Optimize-CodexWorkspace.ps1`.

Detected stack: $stackText

### Validation Commands

$commandLines

### Working Guidelines

- Keep changes scoped to the requested task.
- Inspect existing patterns before introducing new dependencies.
- Run the relevant validation commands before committing.
- Never commit credentials, local environment files, or generated secrets.
$endMarker
"@
}

function Update-AgentsFile {
    param(
        [string]$ManagedSection
    )

    $agentsPath = Join-Path $resolvedProject.Path 'AGENTS.md'
    $existing = if (Test-Path -LiteralPath $agentsPath) {
        Get-Content -LiteralPath $agentsPath -Raw
    }
    else {
        ''
    }
    $pattern = '(?s)' + [regex]::Escape($beginMarker) + '.*?' + [regex]::Escape($endMarker)
    if ($existing -match $pattern) {
        $updated = [regex]::Replace($existing, $pattern, $ManagedSection)
    }
    elseif ($existing) {
        $updated = $existing.TrimEnd() + "`n`n" + $ManagedSection + "`n"
    }
    else {
        $updated = "# AGENTS.md`n`n" + $ManagedSection + "`n"
    }

    if ($PSCmdlet.ShouldProcess($agentsPath, 'Update managed Codex workspace guidance')) {
        Set-Content -LiteralPath $agentsPath -Value $updated -Encoding utf8
    }
    return $agentsPath
}

$resolvedProject = Resolve-Path -LiteralPath $ProjectPath
if (-not (Test-Path -LiteralPath $resolvedProject.Path -PathType Container)) {
    throw "ProjectPath must be a directory: $ProjectPath"
}

$allFiles = @(
    Get-ChildItem -LiteralPath $resolvedProject.Path -Recurse -Force -File -ErrorAction SilentlyContinue |
        Where-Object {
            $relativePath = Get-RelativePath $resolvedProject.Path $_.FullName
            -not (Test-IsExcluded $relativePath)
        }
)
$presentExcludedDirectories = @(
    $excludedDirectories |
        Where-Object { Test-Path -LiteralPath (Join-Path $resolvedProject.Path $_) }
)
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
$stacks = @(Get-DetectedStacks $allFiles)
$validationCommands = @(Get-ValidationCommands $stacks)
$secretFindings = @(Get-SecretFindings $allFiles)
$agentsPath = Join-Path $resolvedProject.Path 'AGENTS.md'
$agentsStatus = if (Test-Path -LiteralPath $agentsPath) { 'present' } else { 'missing' }

if ($Fix) {
    $managedSection = Get-ManagedAgentsSection $stacks $validationCommands
    $agentsPath = Update-AgentsFile $managedSection
    $agentsStatus = 'updated'
}

$report = [ordered]@{
    Timestamp = [DateTime]::UtcNow.ToString('o')
    Project = $resolvedProject.Path
    Stack = $stacks
    FilesInspected = $allFiles.Count
    ValidationCommands = $validationCommands
    AgentsFile = @{
        Path = $agentsPath
        Status = $agentsStatus
    }
    ContextReview = @{
        ExcludedDirectoriesPresent = $presentExcludedDirectories
        LargeFiles = $largeFiles
        ThresholdMB = $MaxFileSizeMB
    }
    SecretScan = @{
        Status = if ($secretFindings.Count -eq 0) { 'passed' } else { 'review-required' }
        Findings = $secretFindings
    }
}

Write-Host 'Codex Workspace Doctor'
Write-Host '----------------------'
Write-Host "Project       : $($report.Project)"
Write-Host "Stack         : $($stacks -join ', ')"
Write-Host "Files checked : $($allFiles.Count)"
Write-Host "AGENTS.md     : $agentsStatus"
Write-Host "Large files   : $($largeFiles.Count)"
Write-Host "Secrets check : $($report.SecretScan.Status)"
Write-Host ''
Write-Host 'Recommended validation commands:'
foreach ($command in $validationCommands) {
    Write-Host "  $command"
}
if ($secretFindings.Count -gt 0) {
    Write-Warning "Review $($secretFindings.Count) possible secret finding(s). Values were intentionally hidden."
    $secretFindings | Format-Table -AutoSize
}

if ($ReportPath) {
    $reportDirectory = Split-Path -Parent $ReportPath
    if ($reportDirectory -and -not (Test-Path -LiteralPath $reportDirectory)) {
        New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
    }
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding utf8
    Write-Host "Report saved  : $ReportPath"
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
