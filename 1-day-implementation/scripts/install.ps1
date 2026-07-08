[CmdletBinding()]
param(
    [ValidateSet("Local", "DockerCompose", "Ansible", "AWS", "Azure")]
    [string]$Mode = "Local",
    [switch]$NoCodex
)

$ErrorActionPreference = "Stop"

Write-Host "Purpose: placeholder installer for the 1 Day Implementation workflow."
Write-Host "Selected deployment mode: $Mode"
if ($NoCodex) {
    Write-Host "Mode: fast operator-only deployment. Codex will not be used."
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Write-Host "Repository root: $repoRoot"

if (-not (Test-Path (Join-Path $repoRoot "README.md"))) {
    throw "README.md not found at repository root."
}

switch ($Mode) {
    "Local" {
        Write-Host "Local mode: use repository scripts directly on the target host."
    }
    "DockerCompose" {
        $composeFile = Join-Path $repoRoot "docker-compose.yml"
        if (-not (Test-Path $composeFile)) {
            throw "docker-compose.yml not found at repository root."
        }
        Write-Host "Docker Compose mode: stack definition found at $composeFile"
    }
    "Ansible" {
        $ansiblePlaybook = Join-Path $repoRoot "ansible\site.yml"
        if (-not (Test-Path $ansiblePlaybook)) {
            throw "Ansible playbook not found at ansible\site.yml."
        }
        Write-Host "Ansible mode: existing-server playbook found at $ansiblePlaybook"
    }
    "AWS" {
        $awsReadme = Join-Path $repoRoot "infra\aws\README.md"
        if (-not (Test-Path $awsReadme)) {
            throw "AWS infra notes not found at infra\aws\README.md."
        }
        Write-Host "AWS mode: cloud provisioning notes found at $awsReadme"
    }
    "Azure" {
        $azureReadme = Join-Path $repoRoot "infra\azure\README.md"
        if (-not (Test-Path $azureReadme)) {
            throw "Azure infra notes not found at infra\azure\README.md."
        }
        Write-Host "Azure mode: cloud provisioning notes found at $azureReadme"
    }
}

Write-Host "No installation changes were applied. Extend this script with explicit, reviewed steps."
exit 0
