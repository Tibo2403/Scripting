$ErrorActionPreference = 'Stop'

$root = 'C:\Users\user\.codex\litellm-proxy'
$python = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$router = Join-Path $root 'risk_adjusted_router.py'

if (-not (Test-Path -LiteralPath $python)) {
  throw "Python runtime not found: $python"
}
if (-not (Test-Path -LiteralPath $router)) {
  throw "Risk router not found: $router"
}

$litellm = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue
if (-not $litellm) {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'start-litellm-proxy.ps1') | Out-Host
}

$existing = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 4001 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
  Write-Output 'Risk-adjusted router is already listening on http://127.0.0.1:4001'
  exit 0
}

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
Start-Process -FilePath $python -ArgumentList @($router) -WorkingDirectory $root -WindowStyle Hidden
Start-Sleep -Seconds 2

try {
  Invoke-RestMethod -Uri 'http://127.0.0.1:4001/health/readiness' -TimeoutSec 5 | ConvertTo-Json -Depth 5
} catch {
  Write-Output 'Risk router started, but readiness did not answer yet. Re-run status-litellm-proxy.ps1 in a few seconds.'
}
