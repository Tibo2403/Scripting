[CmdletBinding()]
param(
    [switch]$NoCodex
)

$ErrorActionPreference = "Stop"

Write-Host "Purpose: placeholder installer for the 1 Day Implementation workflow."
if ($NoCodex) {
    Write-Host "Mode: fast operator-only deployment. Codex will not be used."
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Write-Host "Repository root: $repoRoot"

if (-not (Test-Path (Join-Path $repoRoot "README.md"))) {
    throw "README.md not found at repository root."
}

Write-Host "No installation changes were applied. Extend this script with explicit, reviewed steps."
exit 0
