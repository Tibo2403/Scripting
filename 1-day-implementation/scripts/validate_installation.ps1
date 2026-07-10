[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$requiredFiles = @(
    ".env.example", "docker-compose.yml", "deploy\litellm-config.yaml",
    "ansible\site.yml", "ansible\inventory.example.ini",
    "1-day-implementation\scripts\Manage-OpenClawDeploymentAgents.ps1",
    "1-day-implementation\openclaw\planner\AGENTS.md",
    "1-day-implementation\openclaw\runner\AGENTS.md",
    "1-day-implementation\openclaw\verifier\AGENTS.md"
)
foreach ($relativePath in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $relativePath))) { throw "Required file missing: $relativePath" }
}
$compose = Get-Content -LiteralPath (Join-Path $repoRoot "docker-compose.yml") -Raw
if ($compose -notmatch "127\.0\.0\.1" -or $compose -notmatch "healthcheck:") {
    throw "Compose must retain localhost defaults and health checks."
}
$playbook = Get-Content -LiteralPath (Join-Path $repoRoot "ansible\site.yml") -Raw
if ($playbook -match "Placeholder playbook") { throw "Ansible playbook is still a placeholder." }
Write-Host "Static deployment validation passed."
