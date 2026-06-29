param(
  [int]$Iterations = 5,
  [string[]]$Models = @(
    "codex-light",
    "codex-default",
    "codex-no-openai",
    "codex-risk-adjusted",
    "gemini-flash-direct",
    "codex-qwen-local"
  ),
  [string]$BaseUrl = "http://127.0.0.1:4001/v1",
  [string]$OutputJson = ""
)

$ErrorActionPreference = "Stop"
$root = 'C:\Users\user\.codex\litellm-proxy'

& (Join-Path $root 'measure-litellm-dispatch.ps1') -Iterations $Iterations -Models $Models -BaseUrl $BaseUrl -OutputJson $OutputJson

Write-Host ""
Write-Host "Risk router EWMA state"
Invoke-RestMethod -Uri "http://127.0.0.1:4001/dispatch/metrics" -TimeoutSec 20 | ConvertTo-Json -Depth 10
