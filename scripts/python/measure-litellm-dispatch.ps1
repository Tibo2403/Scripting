param(
  [int]$Iterations = 5,
  [string[]]$Models = @(
    "codex-light",
    "codex-default",
    "codex-no-openai",
    "gemini-flash-direct",
    "codex-qwen-local",
    "codex-local-only"
  ),
  [string]$BaseUrl = "http://127.0.0.1:4000/v1",
  [string]$OutputJson = ""
)

$ErrorActionPreference = "Stop"

function Get-Percentile {
  param([double[]]$Values, [double]$Percentile)
  if ($Values.Count -eq 0) { return $null }
  $sorted = @($Values | Sort-Object)
  if ($sorted.Count -eq 1) { return [math]::Round($sorted[0], 2) }
  $rank = ($Percentile / 100) * ($sorted.Count - 1)
  $lower = [math]::Floor($rank)
  $upper = [math]::Ceiling($rank)
  if ($lower -eq $upper) { return [math]::Round($sorted[$lower], 2) }
  $weight = $rank - $lower
  return [math]::Round(($sorted[$lower] * (1 - $weight)) + ($sorted[$upper] * $weight), 2)
}

function Get-BackendBucket {
  param([string]$Model, [string]$ResponseModel, [string]$LiteLlmModelId)
  $combined = "$ResponseModel $LiteLlmModelId".ToLowerInvariant()
  if ($combined -match "qwen|ollama") { return "qwen_ollama" }
  if ($combined -match "gemini") { return "gemini" }
  if ($combined.Trim().Length -eq 0) { return "unknown" }
  if ($ResponseModel -eq $Model) { return "route_alias" }
  return "other"
}

function Invoke-DispatchProbe {
  param([string]$Model, [int]$Index)
  $payload = @{
    model = $Model
    messages = @(
      @{ role = "system"; content = "Reply with one short sentence." },
      @{ role = "user"; content = "dispatch probe $Index for $Model" }
    )
    max_tokens = 32
    temperature = 0
  } | ConvertTo-Json -Depth 8

  $headers = @{ Authorization = "Bearer local-dev" }
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  try {
    $body = Invoke-RestMethod -Method Post -Uri "$BaseUrl/chat/completions" -ContentType "application/json" -Headers $headers -Body $payload -TimeoutSec 240
    $sw.Stop()
    $responseModel = [string]$body.model
    $modelId = ""
    $bucket = Get-BackendBucket -Model $Model -ResponseModel $responseModel -LiteLlmModelId $modelId
    $fallback = $false
    if ($Model -notin @("codex-qwen-local", "codex-local-only", "gemini-flash-direct", "gemini-pro-direct", "gemini-3.5-flash", "gemini-3.5-pro")) {
      $fallback = ($bucket -eq "qwen_ollama" -or ($responseModel -and $responseModel -ne $Model))
    }
    [pscustomobject]@{
      model = $Model
      iteration = $Index
      ok = $true
      status = 200
      ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 2)
      response_model = $responseModel
      litellm_model_id = $modelId
      backend = $bucket
      fallback = $fallback
      error = $null
    }
  } catch {
    $sw.Stop()
    $status = 0
    $message = $_.Exception.Message
    if ($_.Exception.Response) {
      try { $status = [int]$_.Exception.Response.StatusCode } catch {}
      try {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        $message = $reader.ReadToEnd()
      } catch {}
    }
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
      $message = $_.ErrorDetails.Message
    }
    [pscustomobject]@{
      model = $Model
      iteration = $Index
      ok = $false
      status = $status
      ms = [math]::Round($sw.Elapsed.TotalMilliseconds, 2)
      response_model = ""
      litellm_model_id = ""
      backend = "error"
      fallback = $false
      error = $message
    }
  }
}

Write-Host "Checking proxy readiness at $BaseUrl/models"
Invoke-RestMethod -Uri "$BaseUrl/models" -TimeoutSec 20 | Out-Null

$results = foreach ($model in $Models) {
  foreach ($i in 1..$Iterations) {
    $probe = Invoke-DispatchProbe -Model $model -Index $i
    $statusLabel = if ($probe.ok) { "ok" } else { "fail" }
    Write-Host ("{0,-20} #{1,2} {2,4} {3,8} ms backend={4} response_model={5}" -f $model, $i, $statusLabel, $probe.ms, $probe.backend, $probe.response_model)
    $probe
    Start-Sleep -Milliseconds 250
  }
}

$summary = foreach ($model in $Models) {
  $items = @($results | Where-Object { $_.model -eq $model })
  $success = @($items | Where-Object { $_.ok })
  $latencies = @($success | ForEach-Object { [double]$_.ms })
  $backendCounts = @{}
  foreach ($group in ($success | Group-Object backend)) { $backendCounts[$group.Name] = $group.Count }
  $errorCounts = @{}
  foreach ($group in (@($items | Where-Object { -not $_.ok }) | Group-Object status)) { $errorCounts[[string]$group.Name] = $group.Count }
  $fallbackCount = @($success | Where-Object { $_.fallback }).Count
  [pscustomobject]@{
    model = $model
    total = $items.Count
    pass = $success.Count
    fail = $items.Count - $success.Count
    success_rate = if ($items.Count) { [math]::Round($success.Count / $items.Count, 4) } else { 0 }
    fallback_rate = if ($success.Count) { [math]::Round($fallbackCount / $success.Count, 4) } else { 0 }
    min_ms = Get-Percentile -Values $latencies -Percentile 0
    p50_ms = Get-Percentile -Values $latencies -Percentile 50
    avg_ms = if ($latencies.Count) { [math]::Round(($latencies | Measure-Object -Average).Average, 2) } else { $null }
    p95_ms = Get-Percentile -Values $latencies -Percentile 95
    max_ms = Get-Percentile -Values $latencies -Percentile 100
    served_distribution = $backendCounts
    error_distribution = $errorCounts
  }
}

Write-Host ""
Write-Host "Dispatch summary"
$summary | ConvertTo-Json -Depth 8

if ($OutputJson) {
  $out = [pscustomobject]@{
    generated_at = (Get-Date).ToString("o")
    base_url = $BaseUrl
    iterations = $Iterations
    models = $Models
    summary = $summary
    raw = $results
  }
  $dir = Split-Path -Parent $OutputJson
  if ($dir -and -not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
  }
  $out | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputJson -Encoding UTF8
  Write-Host "Wrote metrics JSON: $OutputJson"
}

