param(
  [ValidateSet('latency-based-routing', 'cost-based-routing', 'usage-based-routing', 'usage-based-routing-v2', 'least-busy', 'simple-shuffle')]
  [string]$RoutingStrategy = 'latency-based-routing',
  [switch]$EnableRiskRouter
)

$ErrorActionPreference = 'Stop'

$root = 'C:\Users\user\.codex\litellm-proxy'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$launcher = Join-Path $root 'start_litellm_proxy.py'
$baseConfig = Join-Path $root 'config.yaml'
$runtimeConfig = Join-Path $root 'config.runtime.yaml'
foreach ($name in @('GEMINI_API_KEY', 'GOOGLE_API_KEY', 'OPENAI_API_KEY', 'HF_TOKEN')) {
  $value = [Environment]::GetEnvironmentVariable($name, 'Process')
  if ([string]::IsNullOrWhiteSpace($value)) {
    $value = [Environment]::GetEnvironmentVariable($name, 'User')
  }
  if (-not [string]::IsNullOrWhiteSpace($value)) {
    [Environment]::SetEnvironmentVariable($name, $value, 'Process')
  }
}

if (-not (Test-Path -LiteralPath $python)) {
  throw "Python runtime not found: $python"
}
if (-not (Test-Path -LiteralPath $launcher)) {
  throw "LiteLLM launcher not found: $launcher"
}
if (-not (Test-Path -LiteralPath $baseConfig)) {
  throw "LiteLLM config not found: $baseConfig"
}

$existing = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
  Write-Output "LiteLLM proxy is already listening on http://127.0.0.1:4000"
  Write-Output "Stop and restart the proxy to change LiteLLM routing_strategy. Requested: $RoutingStrategy"
} else {
  $baseYaml = Get-Content -LiteralPath $baseConfig -Raw
  if ($baseYaml -notmatch '(?m)^\s*routing_strategy:\s*') {
    throw "router_settings.routing_strategy was not found in $baseConfig"
  }
  $runtimeYaml = $baseYaml -replace '(?m)^(\s*routing_strategy:\s*).+$', "`${1}$RoutingStrategy"
  Set-Content -LiteralPath $runtimeConfig -Value $runtimeYaml -Encoding utf8
  Write-Output "LiteLLM native routing_strategy: $RoutingStrategy"

  $env:PYTHONIOENCODING = 'utf-8'
  $env:PYTHONUTF8 = '1'
  Start-Process -FilePath $python -ArgumentList @($launcher, '--config', $runtimeConfig, '--host', '127.0.0.1', '--port', '4000') -WorkingDirectory $root -WindowStyle Hidden
  Start-Sleep -Seconds 5

  try {
    Invoke-RestMethod -Uri 'http://127.0.0.1:4000/health/readiness' -TimeoutSec 5 | ConvertTo-Json -Depth 5
  } catch {
    Write-Output 'Proxy started, but readiness did not answer yet. Re-run status-litellm-proxy.ps1 in a few seconds.'
  }
}

if (-not $EnableRiskRouter) {
  Write-Output 'Risk-adjusted router is optional and was not started. Use -EnableRiskRouter to expose http://127.0.0.1:4001/v1.'
  exit 0
}

$riskRouter = Join-Path $root 'risk_adjusted_router.py'
if (-not (Test-Path -LiteralPath $riskRouter)) {
  throw "Risk-adjusted router not found: $riskRouter"
}

$riskExisting = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 4001 -State Listen -ErrorAction SilentlyContinue
if ($riskExisting) {
  Write-Output 'Risk-adjusted router is already listening on http://127.0.0.1:4001'
  exit 0
}

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
Start-Process -FilePath $python -ArgumentList @($riskRouter) -WorkingDirectory $root -WindowStyle Hidden
Start-Sleep -Seconds 2

try {
  Invoke-RestMethod -Uri 'http://127.0.0.1:4001/health/readiness' -TimeoutSec 5 | ConvertTo-Json -Depth 5
} catch {
  Write-Output 'Risk-adjusted router started, but readiness did not answer yet. Re-run status-litellm-proxy.ps1 in a few seconds.'
}
