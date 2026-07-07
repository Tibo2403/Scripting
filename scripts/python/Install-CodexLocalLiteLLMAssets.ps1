[CmdletBinding()]
param(
    [string]$LiteLLMVersion = '1.91.0',
    [switch]$SkipLiteLLMInstall
)

$ErrorActionPreference = 'Stop'
$target = Join-Path $env:USERPROFILE '.codex\litellm-proxy'
New-Item -ItemType Directory -Force -Path $target | Out-Null

function Get-PythonRuntime {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) {
        return $bundled
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw 'Python 3.10+ est introuvable.'
}

$files = @(
    'litellm-cost-routing.yaml',
    'codex_key_session_web.py',
    'Start-CodexKeySessionWeb.ps1',
    'Start-CodexQwenOllama.ps1',
    'Test-CodexLiteLLMDispatch.ps1',
    'start_litellm_proxy.py',
    'start-litellm-proxy.ps1',
    'stop-litellm-proxy.ps1',
    'status-litellm-proxy.ps1',
    'healthcheck-litellm-routes.ps1',
    'measure-litellm-dispatch.ps1',
    'adaptive_token_pressure_router.py',
    'risk_adjusted_router.py',
    'start-risk-adjusted-router.ps1',
    'stop-risk-adjusted-router.ps1',
    'measure-risk-adjusted-dispatch.ps1',
    'measure-risk-adjusted-streaming.ps1',
    'PRODUCTION_SECURITY_GOVERNANCE.md'
)

foreach ($file in $files) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $target $file) -Force
}

$configSource = Join-Path $PSScriptRoot 'litellm-cost-routing.yaml'
$configTarget = Join-Path $target 'config.yaml'
$text = Get-Content -LiteralPath $configSource -Raw
$text = $text -replace '(?m)^\s*master_key:\s*os\.environ/LITELLM_API_KEY\s*\r?\n',''
Set-Content -LiteralPath $configTarget -Value $text -Encoding UTF8

if (-not $SkipLiteLLMInstall) {
    $pythonRuntime = Get-PythonRuntime
    $venvPath = Join-Path $target 'venv'
    $venvPython = Join-Path $venvPath 'Scripts\python.exe'
    $packageSpec = if ($LiteLLMVersion -eq 'latest') {
        'litellm[proxy]'
    }
    else {
        "litellm[proxy]==$LiteLLMVersion"
    }

    $venvHealthy = $false
    if (Test-Path -LiteralPath $venvPython) {
        & $venvPython -c "print('ok')" 1>$null 2>$null
        $venvHealthy = ($LASTEXITCODE -eq 0)
    }

    if (-not $venvHealthy) {
        if (Test-Path -LiteralPath $venvPath) {
            Write-Output "Recreating broken LiteLLM venv in $venvPath"
            Remove-Item -LiteralPath $venvPath -Recurse -Force
        }
        Write-Output "Creating LiteLLM venv in $venvPath"
        & $pythonRuntime -m venv $venvPath
        if ($LASTEXITCODE -ne 0) {
            throw 'Echec de creation du venv LiteLLM local.'
        }
    }

    Write-Output "Installing $packageSpec in $venvPath"
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw 'Echec de mise a jour de pip dans le venv LiteLLM local.'
    }
    & $venvPython -m pip install --upgrade $packageSpec
    if ($LASTEXITCODE -ne 0) {
        throw 'Echec de installation ou de mise a jour de LiteLLM local.'
    }

    $installedVersion = & $venvPython -c "import importlib.metadata as m; print(m.version('litellm'))"
    Write-Output "LiteLLM installed in ${venvPath}: $installedVersion"
}

Write-Output "Installed local LiteLLM assets in $target"
