[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "Purpose: audit basic repository presence before the 1 Day Implementation workflow."

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Write-Host "Repository root: $repoRoot"

if (-not (Test-Path (Join-Path $repoRoot ".git"))) {
    Write-Host "Warning: .git was not found. Continue only if this is an exported copy."
}

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "README.md"))) {
    throw "README.md not found at repository root."
}

$requiredPaths = @(
    ".env.example",
    "docker-compose.yml",
    "deploy\litellm-config.yaml",
    "ansible\site.yml",
    "ansible\inventory.example.ini",
    "1-day-implementation\scripts\Manage-OpenClawDeploymentAgents.ps1",
    "1-day-implementation\scripts\validate_installation.ps1",
    "1-day-implementation\scripts\Test-OpenClawDeployment.ps1",
    "1-day-implementation\prompts\codex-installation.md",
    "1-day-implementation\prompts\deployment-method-router.md",
    "1-day-implementation\prompts\final-report.md",
    "1-day-implementation\prompts\openclaw-orchestrator.md",
    "1-day-implementation\openclaw\planner\AGENTS.md",
    "1-day-implementation\openclaw\runner\AGENTS.md",
    "1-day-implementation\openclaw\verifier\AGENTS.md"
)

$missingPaths = @(
    foreach ($relativePath in $requiredPaths) {
        if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $relativePath))) {
            $relativePath
        }
    }
)

if ($missingPaths.Count -gt 0) {
    throw "Repository audit failed. Missing required paths: $($missingPaths -join ', ')"
}

$readme = Get-Content -LiteralPath (Join-Path $repoRoot "README.md") -Raw
if ($readme -notmatch "1-day-implementation") {
    throw "README.md should reference the 1-day-implementation workflow."
}

$agentsRoot = Join-Path $repoRoot "1-day-implementation\openclaw"
$agentGuides = Get-ChildItem -Path $agentsRoot -Filter AGENTS.md -Recurse -File
if ($agentGuides.Count -lt 3) {
    throw "Expected planner, runner, and verifier AGENTS.md guides."
}

foreach ($guide in $agentGuides) {
    $content = Get-Content -LiteralPath $guide.FullName -Raw
    if ($content -match "(?i)todo|placeholder") {
        throw "Agent guide still contains TODO or placeholder markers: $($guide.FullName)"
    }
}

Write-Host "Repository audit passed: required deployment files and agent guides are present."
exit 0
