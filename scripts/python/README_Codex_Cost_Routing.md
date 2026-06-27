# Codex Cost Router

Optional cost routing for Codex CLI on Windows using the official open-source
[`BerriAI/litellm`](https://github.com/BerriAI/litellm) proxy.

The local Python wrapper cleans prompts, compresses noisy logs, estimates tokens,
applies budgets, and selects one of these LiteLLM aliases:

- `codex-light` for simple, low-cost and frequent tasks
- `codex-default` for normal coding work
- `codex-long` for long-context reads, log review, and synthesis
- `codex-deep` for difficult debugging, security, and architecture decisions
- `codex-cheap` and `codex-strong` as backward-compatible aliases
- `codex-hf-cheap` for simple Hugging Face / open-model tasks when `HF_TOKEN`
  is set
- `codex-hf-fast` for larger Hugging Face / multi-provider tasks when
  `HF_TOKEN` is set

OpenAI and Gemini are both configured through LiteLLM model groups. The normal
default keeps most code-generation traffic on OpenAI while letting Gemini absorb
long-context and lower-risk work. This reduces token saturation without sending
high-stakes changes blindly to the cheapest model.

API keys are never committed or written to a configuration file. `OPENAI_API_KEY`
is required for the default profile; `GEMINI_API_KEY` is optional but recommended
to activate the OpenAI/Gemini dispatching path.

## Hugging Face Integration

Hugging Face can be used in two optional places.

First, Hugging Face Inference Providers can sit behind LiteLLM as another
provider pool. The local config still includes two optional aliases:

```yaml
codex-hf-cheap -> huggingface/groq/openai/gpt-oss-120b
codex-hf-fast  -> huggingface/together/openai/gpt-oss-120b
```

Set `HF_TOKEN` in the shell before starting the router. A fine-grained token
with Inference Providers permission is enough.

```powershell
$env:HF_TOKEN = 'hf_...'
.\scripts\python\codex-cost-routing.cmd
```

The wrapper can prefer Hugging Face explicitly:

```powershell
python .\scripts\python\codex_cost_router.py run --dry-run `
  --provider huggingface `
  "Benchmark this open model routing task"
```

`--provider auto` routes Hugging Face or multi-provider prompts to the HF aliases
only when `HF_TOKEN` is present. Otherwise it keeps the OpenAI-backed aliases.

LiteLLM also uses `HUGGINGFACE_API_KEY` while resolving some Inference Provider
mappings. The local web session exports the submitted `HF_TOKEN` under both
names for the LiteLLM subprocess. If you start LiteLLM manually, set both names
to the same token:

```powershell
$env:HF_TOKEN = 'hf_...'
$env:HUGGINGFACE_API_KEY = $env:HF_TOKEN
```

## Local Ollama Qwen Fallback

The local LiteLLM config includes `codex-qwen-local` as a final fallback for
the main Codex aliases. It uses Ollama's OpenAI-compatible endpoint with the
lighter Qwen2.5 Coder 7B GGUF model:

```powershell
.\scripts\python\Start-CodexQwenOllama.ps1
```

The script starts Ollama if needed and pulls:

```text
hf.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF:latest
```

LiteLLM then reaches it through `http://127.0.0.1:11434/v1`. No provider API key
is required for this local fallback.

Second, Hugging Face can be added as an optional Codex-facing layer. Running
`enable` now installs two managed profiles:

```text
cost-routing    -> Codex -> local LiteLLM proxy
cost-routing-hf -> Codex -> Hugging Face router
```

The Hugging Face profile uses the OpenAI-compatible endpoint at
`https://router.huggingface.co/v1` with `openai/gpt-oss-120b:fastest` by
default. This is useful when you want a direct open-model path between Codex and
the normal LiteLLM workflow, without starting the local LiteLLM proxy.

```powershell
.\scripts\python\Manage-CodexCostRouting.ps1 -CodexProvider HuggingFace
```

For one-shot wrapper calls, use:

```powershell
python .\scripts\python\codex_cost_router.py run --dry-run `
  --codex-provider huggingface `
  "Use the optional Hugging Face layer for this Codex task"
```

Use `cost-routing` for the normal local proxy path and `cost-routing-hf` only
when you explicitly want Hugging Face between Codex and the rest of the routing
setup.

## Routing Policy

Default routing is controlled by `codex-routing-policy.yaml`. Precedence is:

1. CLI flags such as `--provider` and `--codex-provider`
2. environment variables such as `CODEX_ROUTER_PROVIDER`
3. `codex-routing-policy.yaml`
4. built-in safe defaults

Default policy:

```yaml
default_provider: auto
default_codex_provider: litellm
open_models_only: false
max_cost_usd: 0.0

task_provider_rules:
  simple: auto
  medium: auto
  complex: openai

fallback_order:
  - litellm
  - huggingface
```

`fallback_order` is used for real Codex execution. If the selected Codex-facing
provider is not ready or exits with a non-zero code, the wrapper tries the next
provider in the policy order. A dry-run prints the planned order without calling
Codex.

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
3. asks for the Gemini key with masked input when it is missing; this is optional
   but enables the Gemini model groups;
4. creates a random local `LITELLM_API_KEY` in memory;
5. starts the LiteLLM proxy in the background;
6. enables the optional Codex `cost-routing` profile.
7. opens Codex with that profile;
8. stops LiteLLM and restores the previous configuration when Codex closes.

There is no key to copy and no second terminal is required.

### Optional local web key session

If you prefer entering keys in a local page for one work session, start:

```powershell
.\scripts\python\Start-CodexKeySessionWeb.ps1
```

Then open `http://127.0.0.1:8787/`, paste `OPENAI_API_KEY`,
`GEMINI_API_KEY`, `HF_TOKEN`, or optional custom Qwen endpoint fields, and
submit the form. For the default local Qwen/Ollama fallback, run
`Start-CodexQwenOllama.ps1`; no Qwen API key is needed. The page starts the
LiteLLM proxy on `http://127.0.0.1:4000/v1` with submitted values only in the
proxy process environment. The keys are not written to disk and the web server
suppresses request logging.

To launch the optional Hugging Face-facing profile instead of the local LiteLLM
proxy:

```powershell
.\scripts\python\Manage-CodexCostRouting.ps1 -CodexProvider HuggingFace
```

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

Validate the local proxy aliases without making a paid/model call:

```powershell
.\scripts\python\Test-CodexLiteLLMDispatch.ps1
```

Run a real minimal provider call after entering the relevant key in the local
web page:

```powershell
.\scripts\python\Test-CodexLiteLLMDispatch.ps1 -Model codex-hf-cheap -Call
.\scripts\python\Test-CodexLiteLLMDispatch.ps1 -Model codex-qwen-local -Call
.\scripts\python\Test-CodexLiteLLMDispatch.ps1 -Model codex-default -Call
```

The test prints a compact JSON result and never prints provider tokens.

## Optimized One-Shot Requests

Use the Python wrapper when prompt cleanup and dynamic model routing are needed:

```powershell
python .\scripts\python\codex_cost_router.py run --dry-run "Document this API"
python .\scripts\python\codex_cost_router.py run "Refactor this Python API and add tests"
```

Optional budgets and forced routing:

```powershell
python .\scripts\python\codex_cost_router.py run `
  --force-model codex-deep `
  --provider openai `
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
- `codex_key_session_web.py`: local-only web form for session keys.
- `Start-CodexKeySessionWeb.ps1`: PowerShell launcher for the local key page.
- `Test-CodexLiteLLMDispatch.ps1`: local proxy alias and optional call test.
- `codex-routing-policy.yaml`: editable routing policy and fallback order.
- `litellm-cost-routing.yaml`: local LiteLLM OSS OpenAI/Gemini model groups,
  context-window fallbacks, cooldowns, and compatibility aliases.

## Notes

- LiteLLM runs locally and self-hosted.
- The configuration does not enable LiteLLM Cloud or Enterprise features.
- Actual provider billing remains authoritative.
- The router remains optional: stopping it restores the previous Codex
  `config.toml` byte-for-byte.
