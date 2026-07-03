$ErrorActionPreference = 'Stop'

$switchScript = Join-Path $PSScriptRoot '..\python\Switch-CodexLiteLLM.ps1'
$testRoot = Join-Path $env:TEMP 'codex-litellm-switch-test'
$fakeProfile = Join-Path $testRoot 'profile'
$codexHome = Join-Path $testRoot 'codex-home'
$proxyRoot = Join-Path $fakeProfile '.codex\litellm-proxy'

$previousUserProfile = $env:USERPROFILE
$previousCodexHome = $env:CODEX_HOME
$previousBypass = $env:CODEX_ROUTER_DISABLE_LITELLM

if (Test-Path -LiteralPath $testRoot) {
    Remove-Item -LiteralPath $testRoot -Recurse -Force
}

try {
    New-Item -ItemType Directory -Path $proxyRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $codexHome -Force | Out-Null

    foreach ($name in @('start-litellm-proxy.ps1', 'stop-litellm-proxy.ps1', 'status-litellm-proxy.ps1')) {
        $path = Join-Path $proxyRoot $name
        Set-Content -LiteralPath $path -Value "Write-Output '$name called'" -Encoding UTF8
    }

    $env:USERPROFILE = $fakeProfile
    $env:CODEX_HOME = $codexHome
    Remove-Item Env:\CODEX_ROUTER_DISABLE_LITELLM -ErrorAction SilentlyContinue

    $statusOutput = & $switchScript -Mode Status | Out-String
    if ($statusOutput -notmatch 'status-litellm-proxy.ps1 called') {
        throw 'Status mode did not call the proxy status helper.'
    }
    if ($statusOutput -notmatch 'Codex Cost Router') {
        throw 'Status mode did not call the Python router status command.'
    }

    $onOutput = & $switchScript -Mode On | Out-String
    if ($onOutput -notmatch 'start-litellm-proxy.ps1 called') {
        throw 'On mode did not call the proxy start helper.'
    }
    if ($onOutput -notmatch 'Codex LiteLLM dispatch is ON') {
        throw 'On mode did not report enabled dispatch.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $codexHome 'cost-routing.config.toml'))) {
        throw 'On mode did not create the managed cost-routing profile.'
    }
    if ($env:CODEX_ROUTER_DISABLE_LITELLM) {
        throw 'On mode did not clear the temporary LiteLLM bypass.'
    }

    $offOutput = & $switchScript -Mode Off | Out-String
    if ($offOutput -notmatch 'stop-litellm-proxy.ps1 called') {
        throw 'Off mode did not call the proxy stop helper.'
    }
    if ($offOutput -notmatch 'Codex LiteLLM dispatch is OFF') {
        throw 'Off mode did not report disabled dispatch.'
    }
    if ($env:CODEX_ROUTER_DISABLE_LITELLM -ne '1') {
        throw 'Off mode did not set the temporary LiteLLM bypass.'
    }
    if (Test-Path -LiteralPath (Join-Path $codexHome 'cost-routing.config.toml')) {
        throw 'Off mode did not remove the managed cost-routing profile.'
    }

    Write-Host 'Codex LiteLLM switch smoke test passed.'
}
finally {
    $env:USERPROFILE = $previousUserProfile
    if ($null -eq $previousCodexHome) {
        Remove-Item Env:\CODEX_HOME -ErrorAction SilentlyContinue
    }
    else {
        $env:CODEX_HOME = $previousCodexHome
    }
    if ($null -eq $previousBypass) {
        Remove-Item Env:\CODEX_ROUTER_DISABLE_LITELLM -ErrorAction SilentlyContinue
    }
    else {
        $env:CODEX_ROUTER_DISABLE_LITELLM = $previousBypass
    }
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
