[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "Test-OpenClawDeployment.ps1")
if ($LASTEXITCODE -ne 0) { throw "OpenClaw deployment-agent test failed." }
& (Join-Path $PSScriptRoot "validate_installation.ps1")
if ($LASTEXITCODE -ne 0) { throw "Installation validation failed." }
Write-Host "Quick deployment tests passed."
