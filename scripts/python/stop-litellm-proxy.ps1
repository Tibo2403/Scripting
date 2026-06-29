$riskConnections = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 4001 -State Listen -ErrorAction SilentlyContinue
if ($riskConnections) {
  $riskPids = $riskConnections | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($processId in $riskPids) {
    Stop-Process -Id $processId -Force
    Write-Output "Stopped risk router process $processId"
  }
}
$connections = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue
if (-not $connections) {
  Write-Output 'LiteLLM proxy is not listening on 127.0.0.1:4000'
  exit 0
}

$pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $pids) {
  Stop-Process -Id $processId -Force
  Write-Output "Stopped process $processId"
}

