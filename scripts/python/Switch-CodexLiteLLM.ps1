[CmdletBinding()]
param(
  [ValidateSet('On', 'Off', 'Status')]
  [string]$Mode = 'Status',
  [switch]$Persist
)

$ErrorActionPreference = 'Stop'

$proxyRoot = Join-Path $env:USERPROFILE '.codex\litellm-proxy'
$startProxy = Join-Path $proxyRoot 'start-litellm-proxy.ps1'
$stopProxy = Join-Path $proxyRoot 'stop-litellm-proxy.ps1'
$statusProxy = Join-Path $proxyRoot 'status-litellm-proxy.ps1'
$router = Join-Path $PSScriptRoot 'codex_cost_router.py'
$python = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
  $python = (Get-Command python -ErrorAction Stop).Source
}

function Set-LiteLLMBypass {
  param([string]$Value)

  if ([string]::IsNullOrWhiteSpace($Value)) {
    Remove-Item Env:\CODEX_ROUTER_DISABLE_LITELLM -ErrorAction SilentlyContinue
    if ($Persist) {
      [Environment]::SetEnvironmentVariable('CODEX_ROUTER_DISABLE_LITELLM', $null, 'User')
    }
    return
  }

  $env:CODEX_ROUTER_DISABLE_LITELLM = $Value
  if ($Persist) {
    [Environment]::SetEnvironmentVariable('CODEX_ROUTER_DISABLE_LITELLM', $Value, 'User')
  }
}

switch ($Mode) {
  'On' {
    Set-LiteLLMBypass ''
    & powershell -NoProfile -ExecutionPolicy Bypass -File $startProxy
    & $python $router enable
    Write-Output 'Codex LiteLLM dispatch is ON. Use codex --profile cost-routing, or codex_cost_router.py run --codex-provider litellm.'
    if (-not $Persist) {
      Write-Output 'This shell bypass state is temporary. Add -Persist if you want to remove the bypass from your User environment too.'
    }
  }
  'Off' {
    Set-LiteLLMBypass '1'
    & powershell -NoProfile -ExecutionPolicy Bypass -File $stopProxy
    & $python $router disable
    Write-Output 'Codex LiteLLM dispatch is OFF. Codex will use the normal standard path.'
    if ($Persist) {
      Write-Output 'CODEX_ROUTER_DISABLE_LITELLM=1 was saved in the User environment.'
    }
  }
  'Status' {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $statusProxy
    & $python $router status
    if ($env:CODEX_ROUTER_DISABLE_LITELLM) {
      Write-Output "Current shell bypass: CODEX_ROUTER_DISABLE_LITELLM=$env:CODEX_ROUTER_DISABLE_LITELLM"
    }
    $persisted = [Environment]::GetEnvironmentVariable('CODEX_ROUTER_DISABLE_LITELLM', 'User')
    if ($persisted) {
      Write-Output "Persisted bypass: CODEX_ROUTER_DISABLE_LITELLM=$persisted"
    }
  }
}
