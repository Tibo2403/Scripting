[CmdletBinding()]
param(
    [ValidateSet("Local", "DockerCompose", "Ansible", "AWS", "Azure")][string]$Mode = "Local",
    [switch]$NoCodex,
    [switch]$Apply
)
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Write-Host "Deployment mode: $Mode; apply: $Apply; Codex disabled: $NoCodex"
foreach ($path in @("README.md", "OPENCLAW_TEMP_ORCHESTRATOR.md")) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $path))) { throw "Missing required file: $path" }
}
switch ($Mode) {
    "Local" { Write-Host "Local preflight passed." }
    "DockerCompose" {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker is required." }
        & docker compose -f (Join-Path $repoRoot "docker-compose.yml") --profile app-stack config --quiet
        if ($LASTEXITCODE -ne 0) { throw "Docker Compose configuration validation failed." }
        if ($Apply) {
            $key = [Environment]::GetEnvironmentVariable("LITELLM_MASTER_KEY")
            if ([string]::IsNullOrWhiteSpace($key) -or $key.Length -lt 32 -or $key -like "replace-*") {
                throw "Set LITELLM_MASTER_KEY to a secret of at least 32 characters before apply."
            }
            & docker compose -f (Join-Path $repoRoot "docker-compose.yml") --profile app-stack up -d --wait
            if ($LASTEXITCODE -ne 0) { throw "Docker Compose deployment failed." }
        }
    }
    "Ansible" {
        if (-not (Get-Command ansible-playbook -ErrorAction SilentlyContinue)) { throw "ansible-playbook is required." }
        $inventory = Join-Path $repoRoot "ansible\inventory.ini"
        if (-not (Test-Path -LiteralPath $inventory)) { throw "Copy and review ansible/inventory.example.ini as ansible/inventory.ini." }
        $arguments = @("-i", $inventory, (Join-Path $repoRoot "ansible\site.yml"))
        if ($Apply) { $arguments += @("-e", "deployment_apply=true") }
        & ansible-playbook @arguments
        if ($LASTEXITCODE -ne 0) { throw "Ansible deployment failed." }
    }
    "AWS" { Write-Host "AWS remains plan-only: review infra/aws/README.md first." }
    "Azure" { Write-Host "Azure remains plan-only: review infra/azure/README.md first." }
}
if (-not $Apply) { Write-Host "Preflight complete; no deployment changes were applied." }
