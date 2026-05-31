[CmdletBinding()]
param(
    [ValidateSet('Install', 'Start', 'Run', 'Status', 'Stop')]
    [string]$Action = 'Run',
    [string]$ConfigPath = "$PSScriptRoot\litellm-cost-routing.yaml",
    [string]$VenvPath = 'C:\tmp\litellm-oss',
    [string]$CodexPath,
    [int]$Port = 4000
)

$ErrorActionPreference = 'Stop'
$pidPath = Join-Path $env:TEMP 'codex-litellm-proxy.pid'
$stdoutPath = Join-Path $env:TEMP 'codex-litellm-proxy.out.log'
$stderrPath = Join-Path $env:TEMP 'codex-litellm-proxy.err.log'
$routerPath = Join-Path $PSScriptRoot 'codex_cost_router.py'
$litellmPath = Join-Path $VenvPath 'Scripts\litellm.exe'

function Get-PythonPath {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) {
        return $bundled
    }

    throw 'Python was not found. Install Python 3.10+ before continuing.'
}

function Get-ProxyProcess {
    if (-not (Test-Path -LiteralPath $pidPath)) {
        return $null
    }

    $savedPid = Get-Content -LiteralPath $pidPath -ErrorAction SilentlyContinue
    if (-not $savedPid) {
        return $null
    }

    return Get-Process -Id $savedPid -ErrorAction SilentlyContinue
}

function Test-ProxyPort {
    try {
        $connection = [System.Net.Sockets.TcpClient]::new()
        $connection.Connect('localhost', $Port)
        $connection.Dispose()
        return $true
    }
    catch {
        return $false
    }
}

function Install-LiteLLM {
    if (Test-Path -LiteralPath $litellmPath) {
        Write-Host "LiteLLM OSS is already installed in $VenvPath"
        return
    }

    $python = Get-PythonPath
    Write-Host "Creating a short Windows virtual environment in $VenvPath"
    & $python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to create the LiteLLM virtual environment.'
    }

    Write-Host 'Installing the official BerriAI/litellm OSS proxy package'
    & (Join-Path $VenvPath 'Scripts\python.exe') -m pip install 'litellm[proxy]'
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to install LiteLLM OSS Proxy.'
    }
}

function New-LocalProxyKey {
    return -join ((1..48) | ForEach-Object {
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'[(Get-Random -Maximum 62)]
    })
}

function Start-Proxy {
    param(
        [switch]$ShowManualInstructions
    )
    Install-LiteLLM

    if (Test-ProxyPort) {
        Write-Host "LiteLLM OSS Proxy is already listening on http://localhost:$Port"
        return
    }

    if (-not $env:OPENAI_API_KEY) {
        $secureKey = Read-Host 'Enter your OpenAI API key' -AsSecureString
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        try {
            $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        }
        finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
    }

    if (-not $env:OPENAI_API_KEY) {
        throw 'OPENAI_API_KEY is required.'
    }

    if (-not $env:LITELLM_API_KEY) {
        $env:LITELLM_API_KEY = New-LocalProxyKey
    }

    $resolvedConfig = Resolve-Path -LiteralPath $ConfigPath
    $env:PYTHONUTF8 = '1'
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue

    $process = Start-Process `
        -FilePath $litellmPath `
        -ArgumentList @('--config', $resolvedConfig.Path, '--port', $Port) `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath

    Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ascii

    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline -and -not (Test-ProxyPort)) {
        Start-Sleep -Seconds 2
    }

    if (-not (Test-ProxyPort)) {
        Write-Host "LiteLLM output: $stderrPath"
        throw 'LiteLLM did not start successfully.'
    }

    $python = Get-PythonPath
    & $python $routerPath enable
    if ($LASTEXITCODE -ne 0) {
        throw 'LiteLLM started, but the Codex routing profile could not be enabled.'
    }

    Write-Host ''
    Write-Host "READY: LiteLLM OSS Proxy is listening on http://localhost:$Port"
    if ($ShowManualInstructions) {
        Write-Host 'In the PowerShell window where you will run Codex, paste:'
        Write-Host "  `$env:LITELLM_API_KEY = '$env:LITELLM_API_KEY'"
        Write-Host 'Then run:'
        Write-Host '  codex --profile cost-routing'
    }
    Write-Host ''
    Write-Host 'A browser opened on /health may show Unauthorized. That is expected because the proxy is protected.'
}

function Start-Codex {
    Start-Proxy

    $codexExecutable = $CodexPath
    if (-not $codexExecutable) {
        $codex = Get-Command codex -ErrorAction SilentlyContinue
        if ($codex) {
            $codexExecutable = $codex.Source
        }
    }

    if (-not $codexExecutable) {
        throw 'Codex CLI was not found.'
    }

    Write-Host ''
    Write-Host 'Starting Codex with the cost-routing profile.'
    Write-Host 'Closing Codex will automatically stop LiteLLM and restore the previous Codex configuration.'
    try {
        & $codexExecutable --profile cost-routing
    }
    finally {
        Stop-Proxy
    }
}

function Stop-Proxy {
    $process = Get-ProxyProcess
    if ($process) {
        Stop-Process -Id $process.Id -Force
        Write-Host "Stopped LiteLLM OSS Proxy process $($process.Id)."
    }
    else {
        Write-Host 'LiteLLM OSS Proxy is not running.'
    }

    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
    $python = Get-PythonPath
    & $python $routerPath disable
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:LITELLM_API_KEY -ErrorAction SilentlyContinue
}

function Show-Status {
    $process = Get-ProxyProcess
    Write-Host 'Codex Cost Routing'
    Write-Host '------------------'
    Write-Host "LiteLLM installed : $([bool](Test-Path -LiteralPath $litellmPath))"
    Write-Host "Proxy listening   : $(Test-ProxyPort)"
    Write-Host "Proxy process     : $(if ($process) { $process.Id } else { 'none' })"
    Write-Host "OPENAI_API_KEY    : $(if ($env:OPENAI_API_KEY) { 'set' } else { 'missing' })"
    Write-Host "LITELLM_API_KEY   : $(if ($env:LITELLM_API_KEY) { 'set' } else { 'missing' })"
}

switch ($Action) {
    'Install' { Install-LiteLLM }
    'Start' { Start-Proxy -ShowManualInstructions }
    'Run' { Start-Codex }
    'Status' { Show-Status }
    'Stop' { Stop-Proxy }
}
