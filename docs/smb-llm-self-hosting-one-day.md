# One-Day SMB Self-Hosted LLM Implementation

This runbook gives a small or medium business a practical one-day path to a
self-hosted LLM gateway using the scripting assets in this repository. The goal
is not to replace every cloud model on day one. The goal is to stand up a local
gateway, keep sensitive prompts on a controlled machine when possible, retain
provider fallback for harder tasks, and leave the team with observable,
reversible operations.

## Target Outcome

By the end of the day, the SMB has:

- a local LiteLLM proxy pinned by the repository dependency policy;
- optional local Ollama models for low-risk and offline tasks;
- OpenAI-compatible aliases for simple, normal, long, and deep work;
- adaptive routing that can reduce expensive calls and avoid overloaded routes;
- health checks, dispatch tests, and cost/latency measurement scripts;
- a simple stop path back to standard Codex behavior;
- a short operating checklist for keys, logs, backups, and incidents.

## Reference Architecture

```text
Users and tools
  -> OpenAI-compatible local endpoint
  -> optional risk-adjusted front router on 127.0.0.1:4001
  -> LiteLLM OSS proxy on 127.0.0.1:4000
  -> local Ollama models and approved cloud providers
```

Use local models first for cheap, repeatable, or sensitive low-risk tasks. Use
cloud providers only when the task needs stronger reasoning, larger context, or
business-approved external processing.

## Repository Building Blocks

| Capability | File |
| --- | --- |
| Install local proxy assets | `scripts/python/Install-CodexLocalLiteLLMAssets.ps1` |
| Start, stop, update, and inspect routing | `scripts/python/Manage-CodexCostRouting.ps1` |
| Start LiteLLM with optional adaptive front router | `scripts/python/start-litellm-proxy.ps1` |
| LiteLLM aliases and fallbacks | `scripts/python/litellm-cost-routing.yaml` |
| Prompt compression and provider selection | `scripts/python/codex_cost_router.py` |
| Adaptive TPM/RPM and cost-aware scoring | `scripts/python/adaptive_token_pressure_router.py` |
| Optional front router metrics and retries | `scripts/python/risk_adjusted_router.py` |
| Local dispatch smoke test | `scripts/python/Test-CodexLiteLLMDispatch.ps1` |
| Live route health check | `scripts/python/healthcheck-litellm-routes.ps1` |
| Dispatch timing measurement | `scripts/python/measure-litellm-dispatch.ps1` |
| Adaptive router benchmarks | `scripts/python/measure-risk-adjusted-dispatch.ps1` |
| Simple return to normal routing | `scripts/python/Switch-CodexLiteLLM.ps1` |
| Microsoft 365 operational scripting examples | `scripts/powershell/` |

## One-Day Schedule

### 08:30 - 09:00: Scope and Safety Baseline

Decide which workloads are allowed on the self-hosted LLM path.

Minimum day-one policy:

- allow: code explanation, internal documentation drafts, ticket summaries,
  non-sensitive spreadsheet cleanup, synthetic test data;
- review first: customer data, HR data, legal text, regulated records;
- block: secrets, private keys, raw passwords, payment card data, unredacted
  health data unless the business has an explicit compliant environment.

Record where API keys live. For day one, use session environment variables or
the local key page only. Do not commit keys.

### 09:00 - 10:00: Machine Prep

Use a Windows workstation or small server with:

- PowerShell 5.1+ or PowerShell 7;
- Python 3.12 or the bundled Codex runtime;
- Git;
- optional Docker for Open WebUI or other local UI layers;
- optional Ollama for local models.

Recommended local models for an SMB pilot:

- `qwen2.5-coder:3b` for code and scripting tasks;
- `phi4-mini` for small local drafting and classification tasks;
- a larger local model only if the machine has enough RAM or GPU.

Install or refresh the local proxy assets:

```powershell
cd C:\Users\user\Documents\Scripting
.\scripts\python\Install-CodexLocalLiteLLMAssets.ps1
```

### 10:00 - 11:00: Local Model Path

Start the local Ollama fallback:

```powershell
.\scripts\python\Start-CodexQwenOllama.ps1
```

Verify a direct local response:

```powershell
.\scripts\python\Invoke-QwenLocal.ps1 "Respond with exactly: local llm ready"
```

Measure local speed:

```powershell
.\scripts\python\Measure-QwenLocalSpeed.ps1
```

Decision gate: keep local models for small tasks if responses are usable and
latency is acceptable. Otherwise, keep Ollama as fallback only.

### 11:00 - 12:00: LiteLLM Gateway

Start the proxy with the LiteLLM-backed Codex profile:

```powershell
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Start -CodexProvider LiteLLM
```

Run a no-call proxy alias test:

```powershell
.\scripts\python\Test-CodexLiteLLMDispatch.ps1
```

Run a live minimal call only after the relevant local or cloud backend is ready:

```powershell
.\scripts\python\Test-CodexLiteLLMDispatch.ps1 -Model codex-qwen-local -Call
.\scripts\python\healthcheck-litellm-routes.ps1
```

Expected day-one aliases:

- `codex-light`: cheap/simple work;
- `codex-default`: normal work;
- `codex-long`: long-context tasks;
- `codex-deep`: harder analysis;
- `codex-no-openai`: Gemini plus local fallback when OpenAI should be avoided;
- `codex-qwen-local`: strict local Ollama path.

### 12:00 - 13:00: Adaptive Routing

Start the optional front router when the business wants cost and rate-limit
awareness before requests hit LiteLLM:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  $env:USERPROFILE\.codex\litellm-proxy\start-litellm-proxy.ps1 `
  -EnableRiskRouter
```

Dry-run a routing decision without calling a provider:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:4001/v1/chat/completions `
  -ContentType 'application/json' `
  -Body (@{
    model = 'codex-default'
    dry_run = $true
    messages = @(@{ role = 'user'; content = 'Summarize this internal policy draft' })
  } | ConvertTo-Json -Depth 5)
```

Use adaptive routing when the SMB has mixed workloads and wants to avoid
burning expensive tokens or hitting provider `429` limits during busy periods.

### 13:00 - 14:00: Cost and Reliability Measurements

Capture baseline metrics before pilot users start:

```powershell
.\scripts\python\measure-litellm-dispatch.ps1 -Iterations 5
```

If the adaptive front router is enabled:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  $env:USERPROFILE\.codex\litellm-proxy\measure-risk-adjusted-dispatch.ps1 `
  -Iterations 5

Invoke-RestMethod http://127.0.0.1:4001/dispatch/metrics
Invoke-RestMethod http://127.0.0.1:4001/dispatch/state
```

Track:

- requests per alias;
- estimated tokens per request;
- average and p95 latency;
- 429 count by provider;
- fallback attempts;
- cost per 100 requests;
- user acceptance notes.

### 14:00 - 15:00: SMB Workflow Integration

Pick three practical workflows instead of trying to integrate everything.

Good day-one candidates:

- ticket or email summary with manual review;
- PowerShell script explanation for admins;
- internal knowledge base draft from existing notes;
- meeting-note cleanup with sensitive content removed;
- code review helper for non-production branches.

Use existing PowerShell folders as integration anchors:

- `scripts/powershell/ExchangeOnlineManagement.ps1`;
- `scripts/powershell/TeamsManagement.ps1`;
- `scripts/powershell/SharePointManagement.ps1`;
- `scripts/powershell/UserManagement.ps1`;
- `scripts/powershell/VMManagement.ps1`.

Keep day-one automation human-in-the-loop. The LLM can draft commands or
summaries, but an operator approves changes to tenants, users, mailboxes, files,
or infrastructure.

### 15:00 - 16:00: Security Controls

Minimum controls:

- bind local services to `127.0.0.1` unless there is a reviewed reverse proxy;
- require `LITELLM_API_KEY` for the local proxy;
- keep provider keys in session environment variables or the local key page;
- do not log prompts containing secrets;
- keep spend logs disabled unless a reviewed retention policy exists;
- rotate test keys after the pilot if many people touched the machine;
- stop the proxy when the work session ends.

For shared SMB access, add these before exposing beyond localhost:

- TLS reverse proxy;
- SSO or at least strong basic auth at the edge;
- per-user logging that does not store raw secrets;
- firewall allowlist;
- backups of config files, not keys;
- incident process for leaked prompts or keys.

### 16:00 - 17:00: Pilot, Rollback, and Handoff

Run the pilot with 2-3 users and 10-20 representative prompts.

Acceptance checklist:

- local proxy status is healthy;
- at least one local model call works;
- cloud fallback works only with approved provider keys;
- adaptive dry-run returns a route decision;
- healthcheck shows expected aliases;
- no provider key appears in repo files or console logs;
- stop command restores normal behavior.

Stop and restore:

```powershell
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Stop
.\scripts\python\Switch-CodexLiteLLM.ps1 -Mode Off
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Status
```

Expected final state:

```text
LiteLLM OSS : stopped
Codex profile : standard
temporary proxy key absent
```

## Day-One Deliverables

Create these artifacts for the SMB:

- `LLM_ALLOWED_USE.md`: allowed, review-first, and blocked use cases;
- `LLM_OPERATIONS.md`: start, stop, status, healthcheck, and rollback commands;
- `LLM_METRICS.md`: baseline latency, cost, fallback, and 429 counts;
- `LLM_KEYS.md`: where keys are stored, who can rotate them, and expiry dates;
- `LLM_PILOT_RESULTS.md`: workflows tested, issues, and next actions.

These can live outside the public repo if they contain company-specific
architecture, names, billing, or security details.

## Quick Command Bundle

```powershell
cd C:\Users\user\Documents\Scripting

.\scripts\python\Install-CodexLocalLiteLLMAssets.ps1
.\scripts\python\Start-CodexQwenOllama.ps1
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Start -CodexProvider LiteLLM
.\scripts\python\Test-CodexLiteLLMDispatch.ps1
.\scripts\python\Test-CodexLiteLLMDispatch.ps1 -Model codex-qwen-local -Call
.\scripts\python\healthcheck-litellm-routes.ps1
.\scripts\python\measure-litellm-dispatch.ps1 -Iterations 5
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Stop
```

## Next 30 Days

After the one-day pilot, improve in this order:

1. Add a private web UI for approved users.
2. Add SSO and TLS before any network exposure.
3. Add prompt redaction for secrets and personal data.
4. Add per-workflow routing policies.
5. Add dashboards for cost, latency, and avoided 429s.
6. Expand local models only after measuring real workload quality.
7. Document incident response for leaked prompts, keys, or wrong outputs.

