$riskConnections = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 4001 -State Listen -ErrorAction SilentlyContinue
if ($riskConnections) {
  Write-Output 'Risk-adjusted router on 127.0.0.1:4001'
  $riskConnections | Select-Object LocalAddress,LocalPort,State,OwningProcess
  try {
    Invoke-RestMethod -Uri 'http://127.0.0.1:4001/health/readiness' -TimeoutSec 5 | ConvertTo-Json -Depth 5
    Invoke-RestMethod -Uri 'http://127.0.0.1:4001/dispatch/metrics' -TimeoutSec 5 | ConvertTo-Json -Depth 8
  } catch {
    Write-Output $_.Exception.Message
  }
} else {
  Write-Output 'Risk-adjusted router is not listening on 127.0.0.1:4001'
}

$runtimeConfig = Join-Path $PSScriptRoot 'config.runtime.yaml'
$baseConfig = Join-Path $PSScriptRoot 'config.yaml'
$configToInspect = $baseConfig
if (Test-Path -LiteralPath $runtimeConfig) {
  $configToInspect = $runtimeConfig
}
$strategyLine = Select-String -LiteralPath $configToInspect -Pattern '^\s*routing_strategy:\s*(.+)$' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($strategyLine) {
  Write-Output ("LiteLLM native routing_strategy from {0}: {1}" -f (Split-Path -Leaf $configToInspect), $strategyLine.Matches[0].Groups[1].Value.Trim())
}

$connections = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue
if ($connections) {
  Write-Output 'LiteLLM upstream proxy on 127.0.0.1:4000'
  $connections | Select-Object LocalAddress,LocalPort,State,OwningProcess
  try {
    Invoke-RestMethod -Uri 'http://127.0.0.1:4000/health/readiness' -TimeoutSec 5 | ConvertTo-Json -Depth 5
  } catch {
    Write-Output $_.Exception.Message
  }
} else {
  Write-Output 'LiteLLM proxy is not listening on 127.0.0.1:4000'
}
