# LLM Operations

## Environment

| Field | Value |
| --- | --- |
| Pilot location | Local / Azure / AWS |
| Hostname | TBD |
| Operator | TBD |
| Business owner | TBD |
| Start date | TBD |
| End date | TBD |
| Approved providers | TBD |
| Local models | TBD |

## Preflight

- Confirm `LLM_ALLOWED_USE.md` is approved.
- Confirm keys are stored outside the repository.
- Confirm local, Azure, or AWS access controls are in place.
- Confirm budget alerts are enabled for Azure or AWS.
- Confirm the rollback commands below are available to the operator.

## Start

Run from the repository root:

```powershell
cd C:\Users\user\Documents\Scripting
.\scripts\python\Install-CodexLocalLiteLLMAssets.ps1
.\scripts\python\Start-CodexQwenOllama.ps1
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Start -CodexProvider LiteLLM
```

## Smoke Test

```powershell
.\scripts\python\Test-CodexLiteLLMDispatch.ps1
.\scripts\python\Test-CodexLiteLLMDispatch.ps1 -Model codex-qwen-local -Call
.\scripts\python\healthcheck-litellm-routes.ps1
```

## Optional Adaptive Router

Use this when the pilot needs cost-aware and rate-limit-aware routing before
requests reach LiteLLM.

```powershell
.\scripts\python\start-risk-adjusted-router.ps1
.\scripts\python\measure-risk-adjusted-dispatch.ps1 -Iterations 5
```

Dry-run route decision:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:4001/v1/chat/completions `
  -ContentType 'application/json' `
  -Body (@{
    model = 'codex-default'
    dry_run = $true
    messages = @(@{ role = 'user'; content = 'Summarize this pilot note' })
  } | ConvertTo-Json -Depth 5)
```

## Status

```powershell
.\scripts\python\status-litellm-proxy.ps1
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Status
```

If the adaptive router is enabled:

```powershell
Invoke-RestMethod http://127.0.0.1:4001/dispatch/metrics
Invoke-RestMethod http://127.0.0.1:4001/dispatch/state
```

## Stop and Rollback

```powershell
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Stop
.\scripts\python\Switch-CodexLiteLLM.ps1 -Mode Off
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Status
```

Expected result:

```text
LiteLLM OSS: stopped
Codex profile: standard
temporary proxy key: absent
```

## Incident Actions

429 or provider overload:

- record provider, alias, timestamp, and workload in `LLM_METRICS.md`;
- use adaptive dry-run to check route pressure;
- reduce concurrency or switch workload to a cheaper/local alias.

Suspected prompt or key leak:

- stop routing;
- revoke exposed keys;
- remove exposed material from notes when legally allowed;
- rotate keys;
- record corrective action in `LLM_PILOT_RESULTS.md`.

Unexpected cost increase:

- stop cloud fallback;
- inspect request volume and selected aliases;
- compare against the baseline in `LLM_METRICS.md`;
- re-enable only after owner approval.
