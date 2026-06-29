param(
  [int]$Iterations = 3,
  [string[]]$Models = @(
    "codex-risk-adjusted",
    "codex-default",
    "codex-qwen-local"
  ),
  [string]$BaseUrl = "http://127.0.0.1:4001/v1",
  [int]$MaxTokens = 64
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

function Invoke-StreamingProbe {
  param(
    [string]$Model,
    [string]$BaseUrl,
    [int]$MaxTokens
  )

  $payload = @{
    model = $Model
    stream = $true
    max_tokens = $MaxTokens
    messages = @(
      @{
        role = "user"
        content = "Respond with one compact sentence about route dispatch metrics."
      }
    )
  } | ConvertTo-Json -Depth 10

  $client = [System.Net.Http.HttpClient]::new()
  $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Post, "$BaseUrl/chat/completions")
  $request.Headers.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", "local-dev")
  $request.Content = [System.Net.Http.StringContent]::new($payload, [System.Text.Encoding]::UTF8, "application/json")

  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $firstTokenMs = $null
  $chars = 0
  $status = 0
  $selected = $null
  $errorText = $null

  try {
    $response = $client.SendAsync(
      $request,
      [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead
    ).GetAwaiter().GetResult()
    $status = [int]$response.StatusCode
    if ($response.Headers.Contains("X-Risk-Router-Selected-Model")) {
      $selected = ($response.Headers.GetValues("X-Risk-Router-Selected-Model") | Select-Object -First 1)
    }

    $stream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
    $reader = [System.IO.StreamReader]::new($stream)
    while (-not $reader.EndOfStream) {
      $line = $reader.ReadLine()
      if ([string]::IsNullOrWhiteSpace($line)) {
        continue
      }
      if ($null -eq $firstTokenMs) {
        $firstTokenMs = $sw.Elapsed.TotalMilliseconds
      }
      if ($line.StartsWith("data: ")) {
        $data = $line.Substring(6).Trim()
        if ($data -eq "[DONE]") {
          break
        }
        try {
          $json = $data | ConvertFrom-Json
          $delta = $json.choices[0].delta.content
          if ($delta) {
            $deltaText = [string]$delta
            $chars += $deltaText.Length
          }
        } catch {
          $chars += [Math]::Max(1, [int]($data.Length / 8))
        }
      } else {
        $chars += [Math]::Max(1, [int]($line.Length / 8))
      }
    }
  } catch {
    $errorText = $_.Exception.Message
  } finally {
    $sw.Stop()
    $client.Dispose()
  }

  $tokens = [Math]::Max(0, [int][Math]::Ceiling($chars / 4.0))
  $totalMs = $sw.Elapsed.TotalMilliseconds
  $generationMs = if ($null -ne $firstTokenMs) { [Math]::Max(1.0, $totalMs - $firstTokenMs) } else { [Math]::Max(1.0, $totalMs) }
  $tokensPerSecond = if ($tokens -gt 0) { $tokens / ($generationMs / 1000.0) } else { 0.0 }

  [pscustomobject]@{
    model = $Model
    selected_model = $selected
    status = $status
    ok = ($status -ge 200 -and $status -lt 300)
    ttft_ms = if ($null -ne $firstTokenMs) { [Math]::Round($firstTokenMs, 2) } else { $null }
    total_ms = [Math]::Round($totalMs, 2)
    estimated_completion_tokens = $tokens
    tokens_per_second = [Math]::Round($tokensPerSecond, 2)
    error = $errorText
  }
}

$results = @()
foreach ($model in $Models) {
  for ($i = 1; $i -le $Iterations; $i++) {
    Write-Host "Streaming probe $model [$i/$Iterations]"
    $results += Invoke-StreamingProbe -Model $model -BaseUrl $BaseUrl -MaxTokens $MaxTokens
  }
}

$results | ConvertTo-Json -Depth 10

Write-Host ""
Write-Host "Risk router EWMA state"
Invoke-RestMethod -Uri "http://127.0.0.1:4001/dispatch/metrics" -TimeoutSec 20 | ConvertTo-Json -Depth 10
