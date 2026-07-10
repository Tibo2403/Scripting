[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$json = & (Join-Path $PSScriptRoot "Manage-OpenClawDeploymentAgents.ps1") -Action Plan -Mode DockerCompose -RunId "quick-test"
$plan = $json | ConvertFrom-Json
if ($plan.agents.Count -ne 3) { throw "Expected exactly three temporary deployment agents." }
if (($plan.agents.role -join ",") -ne "planner,runner,verifier") { throw "Unexpected agent roles." }
if (-not $plan.ephemeral -or -not $plan.applyRequired) { throw "The plan must remain ephemeral and approval-gated." }
foreach ($agent in $plan.agents) {
    if (-not (Test-Path -LiteralPath $agent.template)) { throw "Missing template: $($agent.template)" }
    if ($agent.createCommand -notmatch "--non-interactive") { throw "Create command is incomplete." }
    if ($agent.deleteCommand -notmatch "--force$") { throw "Delete command is incomplete." }
}
Write-Host "OpenClaw deployment-agent plan test passed (3 roles, no agent created)."
