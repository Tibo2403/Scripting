$ErrorActionPreference = 'Stop'

$scriptPath = Join-Path $PSScriptRoot '..\python\Manage-CodexCostRouting.ps1'
$testRoot = Join-Path $env:TEMP 'codex-cost-routing-test'
$fakeTemp = Join-Path $testRoot 'temp'
$fakeCodex = Join-Path $testRoot 'fake-codex.cmd'
$pidPath = Join-Path $fakeTemp 'codex-litellm-proxy.pid'
$apiKeyPath = Join-Path $fakeTemp 'codex-litellm-proxy.key'
$stdoutPath = Join-Path $fakeTemp 'codex-litellm-proxy.out.log'
$stderrPath = Join-Path $fakeTemp 'codex-litellm-proxy.err.log'

$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$previousOpenAi = $env:OPENAI_API_KEY
$previousGemini = $env:GEMINI_API_KEY
$previousHf = $env:HF_TOKEN
$previousLiteLLM = $env:LITELLM_API_KEY
$previousUtf8 = $env:PYTHONUTF8

function Invoke-ScriptCapture {
    param(
        [Parameter(Mandatory)]
        [string[]]$ArgumentList
    )

    $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $scriptPath @ArgumentList 2>&1
    return ($output | Out-String)
}

if (Test-Path -LiteralPath $testRoot) {
    Remove-Item -LiteralPath $testRoot -Recurse -Force
}

try {
    New-Item -ItemType Directory -Path $fakeTemp -Force | Out-Null
    Set-Content -LiteralPath $fakeCodex -Value '@echo fake codex invoked' -Encoding ascii

    $env:TEMP = $fakeTemp
    $env:TMP = $fakeTemp
    $env:OPENAI_API_KEY = 'keep-openai'
    $env:GEMINI_API_KEY = 'keep-gemini'
    $env:HF_TOKEN = 'keep-hf'
    $env:LITELLM_API_KEY = 'keep-litellm'
    $env:PYTHONUTF8 = 'invalid-value'

    $statusOutput = Invoke-ScriptCapture -ArgumentList @('-Action', 'Status', '-CodexProvider', 'Standard')
    if ($statusOutput -notmatch 'Codex Cost Routing') {
        throw 'Status output did not include the routing header.'
    }
    if ($statusOutput -notmatch 'LiteLLM OSS : arrete') {
        throw 'Status output did not report the proxy as stopped.'
    }
    if ($env:PYTHONUTF8 -ne 'invalid-value') {
        throw 'Status path did not restore the inherited PYTHONUTF8 value.'
    }

    $startOutput = Invoke-ScriptCapture -ArgumentList @('-Action', 'Start', '-CodexProvider', 'Standard')
    if ($startOutput -notmatch 'rien a activer') {
        throw 'Standard start path did not stay no-op.'
    }

    $runOutput = Invoke-ScriptCapture -ArgumentList @('-Action', 'Run', '-CodexProvider', 'Standard', '-CodexPath', $fakeCodex)
    if ($runOutput -notmatch 'Lancement de Codex par le chemin standard') {
        throw 'Standard run path did not announce the standard launch.'
    }
    if ($runOutput -notmatch 'fake codex invoked') {
        throw 'Standard run path did not invoke the provided codex command.'
    }

    $stopOutput = Invoke-ScriptCapture -ArgumentList @('-Action', 'Stop', '-CodexProvider', 'Standard')
    if ($stopOutput -notmatch 'LiteLLM OSS arrete et configuration Codex restauree') {
        throw 'Stop path did not report cleanup.'
    }

    foreach ($path in @($pidPath, $apiKeyPath, $stdoutPath, $stderrPath)) {
        if (Test-Path -LiteralPath $path) {
            throw "Stop path left behind proxy artifact: $path"
        }
    }

    if ($env:OPENAI_API_KEY -ne 'keep-openai' -or
        $env:GEMINI_API_KEY -ne 'keep-gemini' -or
        $env:HF_TOKEN -ne 'keep-hf' -or
        $env:LITELLM_API_KEY -ne 'keep-litellm') {
        throw 'Standard path unexpectedly mutated session secrets.'
    }

    if ($env:PYTHONUTF8 -ne 'invalid-value') {
        throw 'Nested invocation unexpectedly mutated the parent PYTHONUTF8 value.'
    }

    Write-Host 'Codex cost routing smoke test passed.'
}
finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp

    if ($null -eq $previousOpenAi) { Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue } else { $env:OPENAI_API_KEY = $previousOpenAi }
    if ($null -eq $previousGemini) { Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue } else { $env:GEMINI_API_KEY = $previousGemini }
    if ($null -eq $previousHf) { Remove-Item Env:HF_TOKEN -ErrorAction SilentlyContinue } else { $env:HF_TOKEN = $previousHf }
    if ($null -eq $previousLiteLLM) { Remove-Item Env:LITELLM_API_KEY -ErrorAction SilentlyContinue } else { $env:LITELLM_API_KEY = $previousLiteLLM }
    if ($null -eq $previousUtf8) { Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue } else { $env:PYTHONUTF8 = $previousUtf8 }

    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
