# Codex Cost Router

`codex_cost_router.py` is an optional Windows-friendly wrapper for Codex CLI and
a local, self-hosted LiteLLM OSS proxy. It never stores API keys and does not use
LiteLLM Enterprise or LiteLLM Cloud features.

## Architecture

```text
Optimized one-shot mode:
User -> codex_cost_router.py -> Codex CLI -> LiteLLM OSS -> provider model

Direct profile mode:
User -> Codex CLI --profile cost-routing -> LiteLLM OSS -> codex-auto
```

The Python wrapper is required when you want prompt cleanup and dynamic
`codex-cheap`, `codex-auto`, or `codex-strong` selection. A Codex profile alone
selects the proxy but cannot rewrite every interactive message.

## Requirements

- Python 3.10+
- Codex CLI
- LiteLLM OSS installed locally:

```powershell
pip install "litellm[proxy]"
```

Set keys only in your PowerShell environment:

```powershell
$env:OPENAI_API_KEY = "..."
$env:LITELLM_API_KEY = "local-proxy-key"
```

Do not write keys into committed files.

## Configure LiteLLM OSS

Review `litellm-cost-routing.yaml` and replace deployment model values when
needed. The example defines three aliases and optional fallbacks:

- `codex-cheap`
- `codex-auto`
- `codex-strong`

Start the local proxy:

```powershell
litellm --config .\scripts\python\litellm-cost-routing.yaml --port 4000
```

## Enable Or Disable

Enable the optional profile:

```powershell
python .\scripts\python\codex_cost_router.py enable
```

This copies `plugins/litellm_cost_router.toml` into `%USERPROFILE%\.codex\plugins`
and appends one managed `cost-routing` profile to
`%USERPROFILE%\.codex\config.toml`.

Run Codex directly through the LiteLLM proxy:

```powershell
codex --profile cost-routing
```

Disable the profile without changing unrelated Codex settings:

```powershell
python .\scripts\python\codex_cost_router.py disable
```

On activation, the tool stores a local backup under `%USERPROFILE%\.codex\logs`
so disabling can restore the previous `config.toml` byte-for-byte. The backup
stays on the local machine and is removed after restoration.

The convenience forms `--enable`, `--disable`, and `--status` are also accepted.

## Optimized Routing

Preview routing and compression without calling Codex:

```powershell
python .\scripts\python\codex_cost_router.py run --dry-run "Document this Python API"
```

Optimize a task and invoke `codex exec`:

```powershell
python .\scripts\python\codex_cost_router.py run "Refactor this TypeScript API and add tests"
```

Force an alias or change token budgets:

```powershell
python .\scripts\python\codex_cost_router.py run `
  --force-model codex-strong `
  --max-input-tokens 8000 `
  --max-output-tokens 3000 `
  "Review this production migration for security issues"
```

## Status And Statistics

```powershell
python .\scripts\python\codex_cost_router.py status
python .\scripts\python\codex_cost_router.py history --limit 20
python .\scripts\python\codex_cost_router.py stats
```

Routing records are appended to:

```text
%USERPROFILE%\.codex\logs\cost_router.jsonl
```

The log stores token estimates, routing decisions, execution mode, compression
ratio, and estimated costs. It does not store prompts or API keys.

## Cost Estimates

The Python script uses editable placeholder rates for local estimates. Actual
provider billing remains authoritative. Update `ESTIMATED_RATES` in the script
to match the LiteLLM deployments you configure.

## Notes

- The tool uses only Python standard-library modules.
- The LiteLLM proxy remains fully local and OSS.
- The sample YAML intentionally avoids Enterprise-only settings.
- Provider-specific authentication must be configured through environment
  variables supported by your chosen LiteLLM providers.
