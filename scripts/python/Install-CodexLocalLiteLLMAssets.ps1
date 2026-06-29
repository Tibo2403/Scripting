[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$target = Join-Path $env:USERPROFILE '.codex\litellm-proxy'
New-Item -ItemType Directory -Force -Path $target | Out-Null

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

Write-Output "Installed local LiteLLM assets in $target"
