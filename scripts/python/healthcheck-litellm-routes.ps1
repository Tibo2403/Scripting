$ErrorActionPreference = 'Stop'

$baseUrl = 'http://127.0.0.1:4000'
$apiKeyPath = Join-Path $env:TEMP 'codex-litellm-proxy.key'
$ollamaUrl = 'http://127.0.0.1:11434/api/tags'
$failures = 0

function Pass($Message) { Write-Host "PASS $Message" }
function Fail($Message) { $script:failures += 1; Write-Host "FAIL $Message" }

function Get-LiteLlmApiKey {
  if ($env:LITELLM_API_KEY) {
    return $env:LITELLM_API_KEY
  }
  if (Test-Path -LiteralPath $apiKeyPath) {
    return (Get-Content -LiteralPath $apiKeyPath -Raw).Trim()
  }
  return 'sk-local-codex'
}

function ConvertTo-ShortError {
  param([object]$ErrorRecord)

  $message = $ErrorRecord.Exception.Message
  if ($ErrorRecord.ErrorDetails -and $ErrorRecord.ErrorDetails.Message) {
    $message = $ErrorRecord.ErrorDetails.Message
  }
  if ($message.Length -gt 900) {
    return $message.Substring(0, 900) + '...'
  }
  return $message
}

function Invoke-JsonPost($Uri, $Body) {
  $headers = @{ Authorization = "Bearer $script:apiKey" }
  Invoke-RestMethod -Method Post -Uri $Uri -Headers $headers -ContentType 'application/json' -Body ($Body | ConvertTo-Json -Depth 8) -TimeoutSec 120
}

$script:apiKey = Get-LiteLlmApiKey

if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable('GEMINI_API_KEY', 'User'))) {
  Fail 'GEMINI_API_KEY missing from User environment'
} else {
  Pass 'GEMINI_API_KEY present'
}

try {
  $ready = Invoke-RestMethod -Uri "$baseUrl/health/readiness" -TimeoutSec 10
  Pass "readiness status=$($ready.status)"
} catch {
  Fail "readiness error=$($_.Exception.Message)"
}

try {
  $ollama = Invoke-RestMethod -Uri $ollamaUrl -TimeoutSec 10
  $models = @($ollama.models | ForEach-Object { $_.name })
  if ($models -contains 'qwen2.5-coder:3b') {
    Pass "ollama qwen2.5-coder:3b available models=$($models -join ',')"
  } else {
    Fail "ollama qwen2.5-coder:3b missing models=$($models -join ',')"
  }
} catch {
  Fail "ollama error=$($_.Exception.Message)"
}

$tests = @(
  @{ name = 'codex-light'; model = 'codex-light'; strictProvider = '' },
  @{ name = 'codex-default'; model = 'codex-default'; strictProvider = '' },
  @{ name = 'codex-no-openai'; model = 'codex-no-openai'; strictProvider = '' },
  @{ name = 'codex-qwen-local'; model = 'codex-qwen-local'; strictProvider = 'qwen' }
)

foreach ($test in $tests) {
  try {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $body = @{
      model = $test.model
      messages = @(@{ role = 'user'; content = 'Reply only: ok' })
      max_tokens = 8
      temperature = 0
    }
    $response = Invoke-JsonPost -Uri "$baseUrl/v1/chat/completions" -Body $body
    $sw.Stop()
    $text = $response.choices[0].message.content
    $returned = [string]$response.model

    if ($test.strictProvider -eq 'gemini' -and $returned -notmatch 'gemini') {
      Fail "$($test.name) expected Gemini provider returned=$returned seconds=$([math]::Round($sw.Elapsed.TotalSeconds, 2)) response=$text"
    } elseif ($test.strictProvider -eq 'qwen' -and $returned -notmatch 'qwen|codex-qwen-local') {
      Fail "$($test.name) expected Qwen/local provider returned=$returned seconds=$([math]::Round($sw.Elapsed.TotalSeconds, 2)) response=$text"
    } else {
      Pass "$($test.name) model=$($test.model) returned=$returned seconds=$([math]::Round($sw.Elapsed.TotalSeconds, 2)) response=$text"
    }
  } catch {
    Fail "$($test.name) error=$(ConvertTo-ShortError $_)"
  }
}

Write-Host "SUMMARY failed=$failures"
if ($failures -gt 0) {
  exit 1
}
