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

function Get-ExcludedDirectoryRoot {
    param(
        [string]$RelativePath
    )

    $segments = $RelativePath -split '[\\/]'
    for ($index = 0; $index -lt $segments.Count; $index++) {
        if ($segments[$index] -in $excludedDirectories) {
            return ($segments[0..$index] -join '\')
        }
    }
    return $RelativePath
}

function Get-ProjectInventory {
    $files = [System.Collections.Generic.List[System.IO.FileInfo]]::new()
    $excludedPaths = [System.Collections.Generic.List[string]]::new()
    $reparsePointPaths = [System.Collections.Generic.List[string]]::new()
    $pendingDirectories = [System.Collections.Generic.Stack[System.IO.DirectoryInfo]]::new()
    $pendingDirectories.Push((Get-Item -LiteralPath $resolvedProject.Path))

    while ($pendingDirectories.Count -gt 0) {
        $directory = $pendingDirectories.Pop()
        foreach ($item in Get-ChildItem -LiteralPath $directory.FullName -Force -ErrorAction SilentlyContinue) {
            $relativePath = Get-RelativePath $resolvedProject.Path $item.FullName
            if (-not $item.PSIsContainer) {
                $files.Add($item)
                continue
            }

            if (Test-IsExcluded $relativePath) {
                Add-UniqueValue $excludedPaths (Get-ExcludedDirectoryRoot $relativePath)
                continue
            }
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                $reparsePointPaths.Add($relativePath)
                continue
            }
            $pendingDirectories.Push($item)
        }
    }

    return [ordered]@{
        Files = @($files)
        ExcludedPaths = @($excludedPaths | Sort-Object)
        ReparsePointPaths = @($reparsePointPaths | Sort-Object)
    }
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

function Get-SecretAudit {
    param(
        [System.IO.FileInfo[]]$Files
    )

    $openAiPattern = 's' + 'k-[A-Za-z0-9_-]{20,}'
    $githubPattern = 'gh' + '[pousr]_[A-Za-z0-9]{20,}'
    $awsPattern = 'AK' + 'IA[0-9A-Z]{16}'
    $gitlabPattern = 'gl' + 'pat-[A-Za-z0-9_-]{20,}'
    $slackPattern = 'xo' + 'x[baprs]-[A-Za-z0-9-]{20,}'
    $jwtPattern = 'ey' + 'J[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'
    $assignedPattern = '(?i)\b(password|passwd|api[_-]?key|token|secret)\b\s*[:=]\s*["'']?([^\s"'']{8,})'
    $privateKeyPattern = '-----BEGIN ([A-Z ]+ )?PRIVATE KEY-----'
    $patterns = @(
        @{ Name = 'OpenAI-style API key'; Pattern = $openAiPattern },
        @{ Name = 'GitHub token'; Pattern = $githubPattern },
        @{ Name = 'AWS access key'; Pattern = $awsPattern },
        @{ Name = 'GitLab token'; Pattern = $gitlabPattern },
        @{ Name = 'Slack token'; Pattern = $slackPattern },
        @{ Name = 'JWT token'; Pattern = $jwtPattern },
        @{ Name = 'Assigned secret'; Pattern = $assignedPattern },
        @{ Name = 'Private key'; Pattern = $privateKeyPattern }
    )
    $findings = [System.Collections.Generic.List[object]]::new()
    $skippedLargeFiles = [System.Collections.Generic.List[object]]::new()
    $scannedFileCount = 0

    foreach ($file in $Files) {
        if ($file.Extension -notin $textExtensions -and $file.Name -notin $textNames) {
            continue
        }
        if ($file.Length -gt ($SecretScanMaxFileSizeMB * 1MB)) {
            $skippedLargeFiles.Add([pscustomobject]@{
                Path = Get-RelativePath $resolvedProject.Path $file.FullName
                SizeMB = [math]::Round($file.Length / 1MB, 2)
            })
            continue
        }

        $scannedFileCount++
        $lineNumber = 0
        foreach ($line in Get-Content -LiteralPath $file.FullName -ErrorAction SilentlyContinue) {
            $lineNumber++
            foreach ($pattern in $patterns) {
                if ($line -match $pattern.Pattern) {
                    if ($pattern.Name -eq 'Assigned secret') {
                        $assignedValue = $Matches[2]
                        if ($assignedValue -match '^(\$|os\.environ/|process\.env|import\.meta\.env|Deno\.env|env\[|current\[|Read-Host|e\.target\.value|https?://|<|\$\{|\[REDACTED\])' -or
                            $line -match 'Date\.now\(\)|\bpassword:\s*string\b' -or
                            $assignedValue -match '^[A-Za-z_][A-Za-z0-9_]*[,;]$') {
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
    return [ordered]@{
        Findings = @($findings)
        ScannedFileCount = $scannedFileCount
        SkippedLargeFiles = @($skippedLargeFiles | Sort-Object -Property Path)
    }
}

function ConvertTo-NativeArgument {
    param(
        [string]$Value
    )

    if ($Value -and $Value -notmatch '[\s"]') {
        return $Value
    }
    return '"' + ($Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

function Protect-ValidationLogLine {
    param(
        [string]$Line
    )

    $redacted = $Line
    $redacted = $redacted -replace ('s' + 'k-[A-Za-z0-9_-]{20,}'), '[REDACTED]'
    $redacted = $redacted -replace ('gh' + '[pousr]_[A-Za-z0-9]{20,}'), '[REDACTED]'
    $redacted = $redacted -replace ('AK' + 'IA[0-9A-Z]{16}'), '[REDACTED]'
    $redacted = $redacted -replace ('gl' + 'pat-[A-Za-z0-9_-]{20,}'), '[REDACTED]'
    $redacted = $redacted -replace ('xo' + 'x[baprs]-[A-Za-z0-9-]{20,}'), '[REDACTED]'
    $redacted = $redacted -replace ('ey' + 'J[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'), '[REDACTED]'
    $redacted = $redacted -replace '(?i)\b(password|passwd|api[_-]?key|token|secret)(\s*[:=]\s*["'']?)[^\s"'']{8,}', '$1$2[REDACTED]'
    $redacted = $redacted -replace '-----BEGIN ([A-Z ]+ )?PRIVATE KEY-----', '[REDACTED PRIVATE KEY HEADER]'
    return $redacted
}

function Get-RedactedOutputTail {
    param(
        [string]$Output
    )

    if (-not $Output) {
        return @()
    }
    $lines = @($Output -split '\r?\n' | Where-Object { $_ })
    if ($lines.Count -gt $ValidationLogLineLimit) {
        $lines = @($lines | Select-Object -Last $ValidationLogLineLimit)
    }
    return @($lines | ForEach-Object { Protect-ValidationLogLine $_ })
}

function Stop-ValidationProcess {
    param(
        [System.Diagnostics.Process]$Process
    )

    $childProcessIds = @()
    if ($env:OS -eq 'Windows_NT') {
        $childProcessIds = @(
            Get-CimInstance -ClassName Win32_Process -Filter "ParentProcessId = $($Process.Id)" -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty ProcessId
        )
    }
    foreach ($childProcessId in $childProcessIds) {
        try {
            Stop-ValidationProcess ([System.Diagnostics.Process]::GetProcessById($childProcessId))
        }
        catch {
            # The child may have exited between discovery and termination.
        }
    }
    try {
        if (-not $Process.HasExited) {
            $Process.Kill()
        }
    }
    catch {
        # The process may have exited between the state check and termination.
    }
}

function Invoke-NativeValidation {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    if (-not (Get-Command $Executable -ErrorAction SilentlyContinue)) {
        return [ordered]@{
            Status = 'unavailable'
            ExitCode = $null
            StdOutTail = @()
            StdErrTail = @()
        }
    }

    $resolvedExecutable = Get-Command $Executable -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $resolvedExecutable) {
        $resolvedExecutable = Get-Command $Executable -ErrorAction Stop
    }
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.UseShellExecute = $false
    $startInfo.WorkingDirectory = $resolvedProject.Path
    $nativeArguments = @($Arguments | ForEach-Object { ConvertTo-NativeArgument $_ })
    if ($resolvedExecutable.Source -match '\.(cmd|bat)$') {
        $startInfo.FileName = $env:ComSpec
        $invocation = @(
            ConvertTo-NativeArgument $resolvedExecutable.Source
            $nativeArguments
        ) -join ' '
        $startInfo.Arguments = '/d /s /c "' + $invocation + '"'
    }
    else {
        $startInfo.FileName = $resolvedExecutable.Source
        $startInfo.Arguments = $nativeArguments -join ' '
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $null = $process.Start()
    $stdOutTask = $process.StandardOutput.ReadToEndAsync()
    $stdErrTask = $process.StandardError.ReadToEndAsync()
    $completed = $process.WaitForExit($ValidationTimeoutSeconds * 1000)
    if (-not $completed) {
        Stop-ValidationProcess $process
    }
    $process.WaitForExit()
    $stdOut = $stdOutTask.Result
    $stdErr = $stdErrTask.Result
    $exitCode = if ($completed) { $process.ExitCode } else { $null }
    $status = if (-not $completed) {
        'timed-out'
    }
    elseif ($exitCode -eq 0) {
        'passed'
    }
    else {
        'failed'
    }
    return [ordered]@{
        Status = $status
        ExitCode = $exitCode
        StdOutTail = if ($status -in @('failed', 'timed-out')) { @(Get-RedactedOutputTail $stdOut) } else { @() }
        StdErrTail = if ($status -in @('failed', 'timed-out')) { @(Get-RedactedOutputTail $stdErr) } else { @() }
    }
}

function Invoke-ValidationCommands {
    param(
        [string[]]$Commands,
        [bool]$AllowProjectCommands
    )

    $results = [System.Collections.Generic.List[object]]::new()
    $projectCommandPatterns = @(
        '^python -m pytest$',
        '^npm run (test|lint|build)$',
        '^go test \./\.\.\.$',
        '^cargo test$',
        '^dotnet test$',
        '^mvn test$',
        '^\.\\gradlew test$'
    )
    Push-Location $resolvedProject.Path
    try {
        foreach ($command in $Commands) {
            $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
            $result = $null
            try {
                $isProjectCommand = @(
                    $projectCommandPatterns |
                        Where-Object { $command -match $_ }
                ).Count -gt 0
                if ($isProjectCommand -and -not $AllowProjectCommands) {
                    $result = [ordered]@{
                        Status = 'skipped'
                        ExitCode = $null
                        Reason = 'Requires -AllowProjectCommands for a trusted repository.'
                    }
                }
                else {
                    switch -Regex ($command) {
                    '^python -m pytest$' {
                        $result = Invoke-NativeValidation 'python' @('-m', 'pytest')
                        break
                    }
                    '^python -m compileall \.$' {
                        $result = Invoke-NativeValidation 'python' @('-m', 'compileall', '.')
                        break
                    }
                    '^npm run (test|lint|build)$' {
                        $result = Invoke-NativeValidation 'npm' @('run', $Matches[1])
                        break
                    }
                    '^go test \./\.\.\.$' {
                        $result = Invoke-NativeValidation 'go' @('test', './...')
                        break
                    }
                    '^cargo test$' {
                        $result = Invoke-NativeValidation 'cargo' @('test')
                        break
                    }
                    '^dotnet test$' {
                        $result = Invoke-NativeValidation 'dotnet' @('test')
                        break
                    }
                    '^mvn test$' {
                        $result = Invoke-NativeValidation 'mvn' @('test')
                        break
                    }
                    '^\.\\gradlew test$' {
                        $result = Invoke-NativeValidation '.\gradlew' @('test')
                        break
                    }
                    '^Invoke-ScriptAnalyzer -Path \. -Recurse$' {
                        if (Get-Command Invoke-ScriptAnalyzer -ErrorAction SilentlyContinue) {
                            $findings = @(Invoke-ScriptAnalyzer -Path . -Recurse)
                            $result = [ordered]@{
                                Status = if ($findings.Count -eq 0) { 'passed' } else { 'failed' }
                                ExitCode = if ($findings.Count -eq 0) { 0 } else { 1 }
                            }
                        }
                        else {
                            $result = [ordered]@{
                                Status = 'unavailable'
                                ExitCode = $null
                            }
                        }
                        break
                    }
                    default {
                        $result = [ordered]@{
                            Status = 'skipped'
                            ExitCode = $null
                        }
                    }
                    }
                }
            }
            catch {
                $result = [ordered]@{
                    Status = 'failed'
                    ExitCode = $null
                    StdOutTail = @()
                    StdErrTail = @(Protect-ValidationLogLine $_.Exception.Message)
                }
            }
            finally {
                $stopwatch.Stop()
            }
            $results.Add([pscustomobject]@{
                Command = $command
                Status = $result.Status
                ExitCode = $result.ExitCode
                DurationSeconds = [math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
                Reason = if ($result.Contains('Reason')) { $result.Reason } else { $null }
                StdOutTail = if ($result.Contains('StdOutTail')) { @($result.StdOutTail) } else { @() }
                StdErrTail = if ($result.Contains('StdErrTail')) { @($result.StdErrTail) } else { @() }
            })
        }
    }
    finally {
        Pop-Location
    }
    return @($results)
}

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
        [hashtable]$Readiness
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

function Disable-AgentsFile {
    $agentsPath = Join-Path $resolvedProject.Path 'AGENTS.md'
    if (-not (Test-Path -LiteralPath $agentsPath)) {
        return $agentsPath
    }

    $existing = Get-Content -LiteralPath $agentsPath -Raw
    $pattern = '(?s)\s*' + [regex]::Escape($beginMarker) + '.*?' + [regex]::Escape($endMarker) + '\s*'
    $updated = [regex]::Replace($existing, $pattern, "`n").Trim()
    if ($updated -eq '# AGENTS.md') {
        if ($PSCmdlet.ShouldProcess($agentsPath, 'Remove generated AGENTS.md file')) {
            Remove-Item -LiteralPath $agentsPath -Force
        }
    }
    elseif ($existing -ne $updated) {
        if ($PSCmdlet.ShouldProcess($agentsPath, 'Remove managed Codex workspace guidance')) {
            Set-Content -LiteralPath $agentsPath -Value ($updated + "`n") -Encoding utf8
        }
    }
    return $agentsPath
}

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
$stacks = @(Get-DetectedStacks $allFiles)
$validationCommands = @(Get-ValidationCommands $stacks)
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
    @(Invoke-ValidationCommands $validationCommands $AllowProjectCommands)
}
else {
    @()
}
$efficiency = Get-EfficiencyMetric $readiness $validationResults $Validate
$ciPolicy = Get-CiPolicy $FailOn $secretFindings $validationResults $readiness

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

Write-Host 'Codex Workspace Doctor'
Write-Host '----------------------'
Write-Host "Project       : $($report.Project)"
Write-Host "Stack         : $($stacks -join ', ')"
Write-Host "Files checked : $($allFiles.Count)"
Write-Host "Dirs excluded : $($inventory.ExcludedPaths.Count)"
Write-Host "Links skipped : $($inventory.ReparsePointPaths.Count)"
Write-Host "AGENTS.md     : $agentsStatus"
Write-Host "Large files   : $($largeFiles.Count)"
Write-Host "Secrets check : $($report.SecretScan.Status)"
Write-Host "Secrets files : $($secretAudit.ScannedFileCount) scanned, $($secretAudit.SkippedLargeFiles.Count) skipped"
Write-Host "Git status    : $(if ($gitAudit.IsRepository) { "$($gitAudit.Branch), $($gitAudit.DirtyFileCount) change(s)" } elseif ($gitAudit.Available) { 'not a repository' } else { 'git unavailable' })"
Write-Host "Readiness     : $($readiness.Score)/100"
Write-Host "Efficiency    : $(if ($null -ne $efficiency.Score) { "$($efficiency.Score)/100" } else { $efficiency.Status })"
Write-Host "CI policy     : $($ciPolicy.Status)"
Write-Host ''
Write-Host 'Recommended validation commands:'
foreach ($command in $validationCommands) {
    Write-Host "  $command"
}
if ($Validate) {
    Write-Host ''
    Write-Host 'Validation results:'
    foreach ($validationResult in $validationResults) {
        $reason = if ($validationResult.Reason) { " - $($validationResult.Reason)" } else { '' }
        Write-Host "  $($validationResult.Status): $($validationResult.Command) ($($validationResult.DurationSeconds)s)$reason"
        foreach ($line in @($validationResult.StdOutTail) + @($validationResult.StdErrTail)) {
            Write-Host "    $line"
        }
    }
}
Write-Host ''
Write-Host 'Recommendations:'
foreach ($recommendation in $readiness.Recommendations) {
    Write-Host "  - $recommendation"
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
        Write-Host "Report saved  : $ReportPath"
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
