[CmdletBinding()]
param(
    [int]$UiPort = 8787,
    [int]$ProxyPort = 4000
)

$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw 'Python 3.10+ est introuvable.'
    }
    $pythonPath = $python.Source
}

$scriptPath = Join-Path $PSScriptRoot 'codex_key_session_web.py'
$configPath = Join-Path $PSScriptRoot 'litellm-cost-routing.yaml'
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'config.yaml')) {
    $configPath = Join-Path $PSScriptRoot 'config.yaml'
}

& $pythonPath $scriptPath --ui-port $UiPort --proxy-port $ProxyPort --config $configPath
