[CmdletBinding()]
param(
    [string]$Model = 'qwen2.5-coder:3b',
    [string]$Endpoint = 'http://127.0.0.1:11434/v1/chat/completions',
    [int]$Runs = 3,
    [int]$MaxTokens = 192,
    [double]$Temperature = 0.1,
    [switch]$SkipWarmup
)

$ErrorActionPreference = 'Stop'
if ($Runs -lt 1) {
    throw 'Runs must be >= 1.'
}

function Invoke-QwenBenchPrompt {
    param(
        [string]$Prompt,
        [int]$MaxTokens
    )

    $body = @{
        model = $Model
        messages = @(
            @{
                role = 'system'
                content = 'Tu es un assistant code local. Reponds avec du code ou des points courts.'
            },
            @{
                role = 'user'
                content = $Prompt
            }
        )
        temperature = $Temperature
        max_tokens = $MaxTokens
        stream = $false
    } | ConvertTo-Json -Depth 8

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $response = Invoke-RestMethod -Method Post -Uri $Endpoint -ContentType 'application/json' -Body $body
    $stopwatch.Stop()

    $completionTokens = 0
    if ($response.usage -and $response.usage.completion_tokens) {
        $completionTokens = [int]$response.usage.completion_tokens
    }
    elseif ($response.usage -and $response.usage.total_tokens -and $response.usage.prompt_tokens) {
        $completionTokens = [int]$response.usage.total_tokens - [int]$response.usage.prompt_tokens
    }

    $elapsedSeconds = [Math]::Max($stopwatch.Elapsed.TotalSeconds, 0.001)
    [pscustomobject]@{
        tokens = $completionTokens
        seconds = $elapsedSeconds
        tok_s = if ($completionTokens -gt 0) { $completionTokens / $elapsedSeconds } else { 0 }
    }
}

if (-not $SkipWarmup) {
    Write-Host "Warmup $Model..."
    [void](Invoke-QwenBenchPrompt -Prompt 'Reponds simplement: OK.' -MaxTokens 16)
}

$prompt = @(
    'Refactorise ce petit code Python pour le rendre plus lisible, puis donne deux tests unitaires pytest:',
    '',
    'def f(xs):',
    '    r=[]',
    '    for x in xs:',
    '        if x and x>0:',
    '            r.append(x*x)',
    '    return r'
) -join [Environment]::NewLine

$results = @()
foreach ($run in 1..$Runs) {
    Write-Host "Run $run/$Runs..."
    $result = Invoke-QwenBenchPrompt -Prompt $prompt -MaxTokens $MaxTokens
    $results += [pscustomobject]@{
        run = $run
        tokens = $result.tokens
        seconds = [Math]::Round($result.seconds, 3)
        tok_s = [Math]::Round($result.tok_s, 3)
    }
}

$totalTokens = ($results | Measure-Object -Property tokens -Sum).Sum
$totalSeconds = ($results | Measure-Object -Property seconds -Sum).Sum
$weightedTokS = if ($totalSeconds -gt 0) { $totalTokens / $totalSeconds } else { 0 }

$results | Format-Table -AutoSize
Write-Host ("Weighted: {0:N3} tok/s ({1} completion tokens in {2:N3}s)" -f $weightedTokS, $totalTokens, $totalSeconds)
