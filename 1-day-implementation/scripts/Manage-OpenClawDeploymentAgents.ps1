[CmdletBinding()]
param(
    [ValidateSet("Plan", "Create", "Delete")][string]$Action = "Plan",
    [ValidateSet("Local", "DockerCompose", "Ansible", "AWS", "Azure")][string]$Mode = "DockerCompose",
    [ValidatePattern("^[a-zA-Z0-9-]+$")][string]$RunId = (Get-Date -Format "yyyyMMdd-HHmmss"),
    [string]$WorkspaceRoot = (Join-Path ([System.IO.Path]::GetTempPath()) "openclaw-deployment-agents"),
    [string]$OpenClawCommand = "openclaw",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$templateRoot = Join-Path $repoRoot "1-day-implementation\openclaw"
$agents = foreach ($role in @("planner", "runner", "verifier")) {
    $name = "deploy-$RunId-$role".ToLowerInvariant()
    $workspace = Join-Path (Join-Path $WorkspaceRoot $RunId) $role
    [ordered]@{
        role = $role; name = $name; workspace = $workspace
        template = Join-Path (Join-Path $templateRoot $role) "AGENTS.md"
        createCommand = "$OpenClawCommand agents add $name --workspace `"$workspace`" --non-interactive"
        deleteCommand = "$OpenClawCommand agents delete $name --force"
    }
}

if ($Action -eq "Plan") {
    [ordered]@{ runId = $RunId; mode = $Mode; ephemeral = $true; applyRequired = $true; agents = @($agents) } |
        ConvertTo-Json -Depth 5
    exit 0
}
if (-not $Apply) { throw "$Action is mutating. Review -Action Plan, then repeat with -Apply." }
if (-not (Get-Command $OpenClawCommand -ErrorAction SilentlyContinue)) { throw "OpenClaw command not found: $OpenClawCommand" }

if ($Action -eq "Create") {
    foreach ($agent in $agents) {
        if (-not (Test-Path -LiteralPath $agent.template)) { throw "Agent template missing: $($agent.template)" }
        New-Item -ItemType Directory -Path $agent.workspace -Force | Out-Null
        Copy-Item -LiteralPath $agent.template -Destination (Join-Path $agent.workspace "AGENTS.md") -Force
        & $OpenClawCommand agents add $agent.name --workspace $agent.workspace --non-interactive
        if ($LASTEXITCODE -ne 0) { throw "OpenClaw failed to create agent $($agent.name)." }
    }
    Write-Host "Created $($agents.Count) temporary agents for $Mode."
    exit 0
}

foreach ($agent in $agents) {
    & $OpenClawCommand agents delete $agent.name --force
    if ($LASTEXITCODE -ne 0) { throw "OpenClaw failed to delete agent $($agent.name)." }
}
$resolvedRoot = [System.IO.Path]::GetFullPath($WorkspaceRoot).TrimEnd('\')
$runWorkspace = [System.IO.Path]::GetFullPath((Join-Path $WorkspaceRoot $RunId))
if (-not $runWorkspace.StartsWith($resolvedRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean a workspace outside WorkspaceRoot."
}
if (Test-Path -LiteralPath $runWorkspace) { Remove-Item -LiteralPath $runWorkspace -Recurse -Force }
Write-Host "Deleted $($agents.Count) temporary agents and their run workspace."
