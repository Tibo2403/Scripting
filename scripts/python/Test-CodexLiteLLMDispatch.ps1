[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:4000/v1",
    [string]$ApiKey = "",
    [string]$Model = "codex-default",
    [switch]$Call,
    [switch]$AllowDefaultKey,
    [int]$TimeoutSec = 90
)

$ErrorActionPreference = "Stop"
$apiKeyPath = Join-Path $env:TEMP "codex-litellm-proxy.key"
$apiKeySource = "parameter"

if (-not $ApiKey) {
    if ($env:LITELLM_API_KEY) {
        $ApiKey = $env:LITELLM_API_KEY
        $apiKeySource = "environment"
    }
    elseif (Test-Path -LiteralPath $apiKeyPath) {
        $ApiKey = (Get-Content -LiteralPath $apiKeyPath -Raw).Trim()
        $apiKeySource = "temp-file"
    }
    else {
        $ApiKey = "sk-local-codex"
        $apiKeySource = "default"
    }
}

if ($Call -and $apiKeySource -eq "default" -and -not $AllowDefaultKey) {
    [pscustomobject]@{
        ok = $false
        base_url = $BaseUrl
        api_key_source = $apiKeySource
        error = "Live calls require LITELLM_API_KEY, %TEMP%\codex-litellm-proxy.key, -ApiKey, or explicit -AllowDefaultKey."
    } | ConvertTo-Json -Depth 4
    exit 2
}

$headers = @{
    "Authorization" = "Bearer $ApiKey"
    "Content-Type" = "application/json"
}

function ConvertTo-ShortError {
    param([object]$ErrorRecord)

    $message = $ErrorRecord.Exception.Message
    if ($ErrorRecord.ErrorDetails -and $ErrorRecord.ErrorDetails.Message) {
        $message = $ErrorRecord.ErrorDetails.Message
    }
    if ($message.Length -gt 900) {
        return $message.Substring(0, 900) + "..."
    }
    return $message
}

function Get-DispatchErrorKind {
    param([string]$Message)

    if ($Message -match 'RESOURCE_EXHAUSTED|RateLimitError|quota|429') {
        return 'provider_rate_limited'
    }
    if ($Message -match 'AuthenticationError|401|403|invalid.*key|api.?key') {
        return 'provider_auth_failed'
    }
    if ($Message -match 'Connection error|Unable to connect|No connection could be made|connection refused') {
        return 'provider_unreachable'
    }
    if ($Message -match 'Not allowed to POST|BadRequestError') {
        return 'provider_incompatible'
    }
    return 'provider_error'
}

$models = Invoke-RestMethod -Uri "$BaseUrl/models" -Headers $headers -Method Get -TimeoutSec 10
$modelIds = @($models.data | ForEach-Object { $_.id })
$requiredAliases = @(
    "codex-light",
    "codex-default",
    "codex-long",
    "codex-deep",
    "codex-qwen-local",
    "codex-hf-cheap",
    "codex-hf-fast"
)
$missingAliases = @($requiredAliases | Where-Object { $modelIds -notcontains $_ })

$health = $null
try {
    $healthUrl = $BaseUrl -replace "/v1$", ""
    $health = Invoke-RestMethod -Uri "$healthUrl/health" -Headers $headers -Method Get -TimeoutSec $TimeoutSec
}
catch {
    $health = [pscustomobject]@{
        healthy_count = $null
        unhealthy_count = $null
        health_error = ConvertTo-ShortError $_
    }
}

$callResult = $null
if ($Call) {
    $body = @{
        model = $Model
        messages = @(
            @{
                role = "user"
                content = "Reply with exactly: dispatch ok"
            }
        )
        max_tokens = 16
        temperature = 0
    } | ConvertTo-Json -Depth 6

    try {
        $response = Invoke-RestMethod -Uri "$BaseUrl/chat/completions" -Headers $headers -Method Post -Body $body -TimeoutSec $TimeoutSec
        $callResult = [pscustomobject]@{
            ok = $true
            model = $response.model
            content = $response.choices[0].message.content
        }
    }
    catch {
        $shortError = ConvertTo-ShortError $_
        $callResult = [pscustomobject]@{
            ok = $false
            kind = Get-DispatchErrorKind -Message $shortError
            error = $shortError
        }
    }
}

$proxyOk = ($missingAliases.Count -eq 0 -and -not $health.health_error)
$providersOk = (-not $Call -or ($callResult -and $callResult.ok))

[pscustomobject]@{
    ok = ($proxyOk -and $providersOk)
    proxy_ok = $proxyOk
    providers_ok = $providersOk
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
    base_url = $BaseUrl
    api_key_source = $apiKeySource
    live_call_enabled = [bool]$Call
    aliases_present = @($requiredAliases | Where-Object { $modelIds -contains $_ })
    aliases_missing = $missingAliases
    healthy_count = $health.healthy_count
    unhealthy_count = $health.unhealthy_count
    health_error = $health.health_error
    call = $callResult
} | ConvertTo-Json -Depth 6
