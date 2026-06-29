$connections = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 4001 -State Listen -ErrorAction SilentlyContinue
if (-not $connections) {
  Write-Output 'Risk-adjusted router is not listening on 127.0.0.1:4001'
  exit 0
}

$pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $pids) {
  Stop-Process -Id $processId -Force
  Write-Output "Stopped risk router process $processId"
}
