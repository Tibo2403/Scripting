[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$target = Join-Path $env:USERPROFILE '.codex\litellm-proxy'
New-Item -ItemType Directory -Force -Path $target | Out-Null

$files = @(
    'litellm-cost-routing.yaml',
    'codex_key_session_web.py',
    'Start-CodexKeySessionWeb.ps1'
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
