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

# Private helpers loaded in Optimize-CodexWorkspace.ps1 script scope.

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

function Get-DetectedStack {
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

function Get-ValidationCommand {
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
