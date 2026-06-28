[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Prompt,
    [string]$Model = 'qwen2.5-coder:3b',
    [string]$Endpoint = 'http://127.0.0.1:11434/v1/chat/completions',
    [int]$MaxTokens = 512,
    [double]$Temperature = 0.1,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$promptText = $Prompt.Trim()
if (-not $promptText) {
    throw 'Prompt is required.'
}

$body = @{
    model = $Model
    messages = @(
        @{
            role = 'system'
            content = 'Tu es un assistant local pour le code. Reponds de facon concise, concrete, et directement exploitable.'
        },
        @{
            role = 'user'
            content = $promptText
        }
    )
    temperature = $Temperature
    max_tokens = $MaxTokens
    stream = $false
} | ConvertTo-Json -Depth 8

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$response = Invoke-RestMethod -Method Post -Uri $Endpoint -ContentType 'application/json' -Body $body
$stopwatch.Stop()

$content = ''
if ($response.choices -and $response.choices.Count -gt 0) {
    $content = [string]$response.choices[0].message.content
}

$completionTokens = 0
if ($response.usage -and $response.usage.completion_tokens) {
    $completionTokens = [int]$response.usage.completion_tokens
}
elseif ($response.usage -and $response.usage.total_tokens -and $response.usage.prompt_tokens) {
    $completionTokens = [int]$response.usage.total_tokens - [int]$response.usage.prompt_tokens
}

$elapsedSeconds = [Math]::Max($stopwatch.Elapsed.TotalSeconds, 0.001)
$tokensPerSecond = if ($completionTokens -gt 0) {
    $completionTokens / $elapsedSeconds
}
else {
    0
}

if ($Json) {
    [pscustomobject]@{
        model = $Model
        elapsed_s = [Math]::Round($elapsedSeconds, 3)
        completion_tokens = $completionTokens
        tok_s = [Math]::Round($tokensPerSecond, 3)
        content = $content
    } | ConvertTo-Json -Depth 4
}
else {
    Write-Output $content
    Write-Output ''
    Write-Output ("# {0} | {1} completion tokens | {2:N2} tok/s | {3:N2}s" -f $Model, $completionTokens, $tokensPerSecond, $elapsedSeconds)
}
