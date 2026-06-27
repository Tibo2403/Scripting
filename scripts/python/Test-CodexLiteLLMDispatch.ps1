[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:4000/v1",
    [string]$ApiKey = "sk-local-codex",
    [string]$Model = "codex-default",
    [switch]$Call,
    [int]$TimeoutSec = 90
)

$ErrorActionPreference = "Stop"

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
        $callResult = [pscustomobject]@{
            ok = $false
            error = ConvertTo-ShortError $_
        }
    }
}

[pscustomobject]@{
    ok = ($missingAliases.Count -eq 0 -and (-not $Call -or ($callResult -and $callResult.ok)))
    base_url = $BaseUrl
    aliases_present = @($requiredAliases | Where-Object { $modelIds -contains $_ })
    aliases_missing = $missingAliases
    healthy_count = $health.healthy_count
    unhealthy_count = $health.unhealthy_count
    health_error = $health.health_error
    call = $callResult
} | ConvertTo-Json -Depth 6
