# Codex Cost Router

Optional cost routing for Codex CLI on Windows using the official open-source
[`BerriAI/litellm`](https://github.com/BerriAI/litellm) proxy.

The local Python wrapper cleans prompts, compresses noisy logs, estimates tokens,
applies budgets, and selects one of these LiteLLM aliases:

- `codex-cheap` for simple, low-cost tasks
- `codex-strong` for default, medium, and complex tasks

The previous `codex-auto` middle tier was removed because it pointed to the same
provider model as `codex-strong`, which made the fallback chain redundant. Add a
third alias again only when it maps to a genuinely different model or provider.

API keys are never committed or written to a configuration file.

## Quick Start

Open PowerShell in the repository:

```powershell
cd C:\Users\user\Documents\Scripting
```

Start LiteLLM and Codex with one command:

```powershell
.\scripts\python\codex-cost-routing.cmd
```

The launcher automatically bypasses restrictive PowerShell execution policies
for this command only. The script:

1. installs the official LiteLLM OSS proxy in `C:\tmp\litellm-oss` when needed;
2. asks for the OpenAI key with masked input when it is missing;
3. creates a random local `LITELLM_API_KEY` in memory;
4. starts the LiteLLM proxy in the background;
5. enables the optional Codex `cost-routing` profile.
6. opens Codex with that profile;
7. stops LiteLLM and restores the previous configuration when Codex closes.

There is no key to copy and no second terminal is required.

Stop and restore the Codex configuration after an interrupted session:

```powershell
.\scripts\python\codex-cost-routing.cmd Stop
```

## Status

```powershell
.\scripts\python\codex-cost-routing.cmd Status
python .\scripts\python\codex_cost_router.py doctor
```

If a browser opened on `http://localhost:4000/health` shows `Unauthorized`,
that is expected: the local proxy is protected by `LITELLM_API_KEY`.

## Optimized One-Shot Requests

Use the Python wrapper when prompt cleanup and dynamic model routing are needed:

```powershell
python .\scripts\python\codex_cost_router.py run --dry-run "Document this API"
python .\scripts\python\codex_cost_router.py run "Refactor this Python API and add tests"
```

Optional budgets and forced routing:

```powershell
python .\scripts\python\codex_cost_router.py run `
  --force-model codex-strong `
  --max-input-tokens 8000 `
  --max-output-tokens 3000 `
  "Review this production migration for security issues"
```

## History

```powershell
python .\scripts\python\codex_cost_router.py history --limit 20
python .\scripts\python\codex_cost_router.py stats
```

Routing metadata is written to:

```text
%USERPROFILE%\.codex\logs\cost_router.jsonl
```

Prompts and API keys are not logged.

## Files

- `Manage-CodexCostRouting.ps1`: automatic run, status, and stop workflow.
- `codex-cost-routing.cmd`: simple Windows launcher.
- `codex_cost_router.py`: prompt optimization and one-shot routing.
- `litellm-cost-routing.yaml`: local LiteLLM OSS model aliases and fallback.

## Notes

- LiteLLM runs locally and self-hosted.
- The configuration does not enable LiteLLM Cloud or Enterprise features.
- Actual provider billing remains authoritative.
- The router remains optional: stopping it restores the previous Codex
  `config.toml` byte-for-byte.
