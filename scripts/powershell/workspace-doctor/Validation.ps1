# Private helpers loaded in Optimize-CodexWorkspace.ps1 script scope.

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
    [CmdletBinding(SupportsShouldProcess)]
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
            Write-Verbose "Child process termination failed: $($_.Exception.Message)"
        }
    }
    try {
        if (-not $Process.HasExited -and $PSCmdlet.ShouldProcess($Process.Id, 'Terminate timed-out validation')) {
            $Process.Kill()
        }
    }
    catch {
        if (-not $Process.HasExited) { throw }
        Write-Verbose 'Validation process exited during termination.'
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
        $startInfo.FileName = if ($env:ComSpec) { $env:ComSpec } else { 'cmd.exe' }
        $invocation = @(
            ConvertTo-NativeArgument $resolvedExecutable.Source
            $nativeArguments
        ) -join ' '
        $startInfo.Arguments = '/d /c ' + $invocation
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

function Invoke-ValidationCommand {
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
