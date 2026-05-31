[CmdletBinding()]
param(
    [string]$ConfigPath = "$PSScriptRoot\litellm-cost-routing.yaml",
    [int]$Port = 4000
)

$ErrorActionPreference = 'Stop'
$fallback = 'C:\tmp\litellm-oss\Scripts\litellm.exe'
$litellm = Get-Command litellm -ErrorAction SilentlyContinue

if (-not $litellm -and (Test-Path -LiteralPath $fallback)) {
    $litellm = Get-Item -LiteralPath $fallback
}

if (-not $litellm) {
    throw 'LiteLLM OSS Proxy is not installed. See README_Codex_Cost_Routing.md.'
}

if (-not $env:OPENAI_API_KEY) {
    throw 'OPENAI_API_KEY is missing. Set it in this PowerShell session before starting LiteLLM.'
}

if (-not $env:LITELLM_API_KEY) {
    throw 'LITELLM_API_KEY is missing. Set a local proxy key in this PowerShell session before starting LiteLLM.'
}

$resolvedConfig = Resolve-Path -LiteralPath $ConfigPath
$env:PYTHONUTF8 = '1'
$litellmPath = if ($litellm.Source) { $litellm.Source } else { $litellm.FullName }

Write-Host "Starting LiteLLM OSS Proxy on http://localhost:$Port"
Write-Host "Health endpoint: http://localhost:$Port/health"
& $litellmPath --config $resolvedConfig.Path --port $Port
