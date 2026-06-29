# Codex Cost Router

Optional routing for Codex CLI on Windows. The default path is the normal Codex CLI. LiteLLM is an opt-in proxy used when you want Gemini API dispatch or a shared gateway to local Qwen.

The local Python wrapper cleans prompts, compresses noisy logs, estimates tokens,
applies budgets, and selects one of these LiteLLM aliases:

- `codex-light` for simple, low-cost and frequent tasks
- `codex-default` for normal coding work
- `codex-long` for long-context reads, log review, and synthesis
- `codex-deep` for difficult debugging, security, and architecture decisions
- `codex-no-openai` for Gemini + local Qwen routing when OpenAI quota is low
  or exhausted
- `codex-cheap` and `codex-strong` as backward-compatible aliases
- `codex-hf-cheap` for simple Hugging Face / open-model tasks when `HF_TOKEN`
  is set
- `codex-hf-fast` for larger Hugging Face / multi-provider tasks when
  `HF_TOKEN` is set

Gemini and local Qwen are configured through LiteLLM model groups when the proxy is active. Without the proxy, the wrapper keeps the standard Codex path and can still call local Qwen directly through Ollama for selected local tasks.

Provider API keys are never committed or written to a configuration file.
`GEMINI_API_KEY` is only needed for Gemini dispatch through LiteLLM. Local Qwen
only needs Ollama running with `qwen2.5-coder:3b` installed. The local proxy
master key is generated per session and written only to
`%TEMP%\codex-litellm-proxy.key` so local test scripts can authenticate; it is
removed when the proxy stops.

## OpenAI Quota Saver

When OpenAI quota is low or exhausted, use the `codex-no-openai` alias. It routes
through Gemini first and local Qwen second, without OpenAI entries in the model
group:

```powershell
codex --model codex-no-openai
```

For one-shot wrapper calls, either force the provider:

```powershell
python .\scripts\python\codex_cost_router.py run --dry-run `
  --provider no-openai `
  "Refactor this Python API without using OpenAI quota"
```

or set a temporary session mode:

```powershell
$env:CODEX_ROUTER_OPENAI_MODE = 'avoid'
python .\scripts\python\codex_cost_router.py run --dry-run `
  "Refactor this Python API without using OpenAI quota"
```

For a durable default, set `avoid_openai: true` in
`codex-routing-policy.yaml`.

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
Qwen2.5 Coder 3B model:

```powershell
.\scripts\python\Start-CodexQwenOllama.ps1
```

The script starts Ollama if needed and pulls:

```text
qwen2.5-coder:3b
```

LiteLLM then reaches it through `http://127.0.0.1:11434/v1`. No provider API key
is required for this local fallback.
### Local Fast Path

For the fastest local path, call Ollama directly instead of going through
LiteLLM. This is the preferred path for quick code cleanup, small explanations,
and local smoke checks:

```powershell
.\scripts\python\Invoke-QwenLocal.ps1 "Nettoie ce code Python et explique le changement: def f(x): return x+1"
```

Measure local throughput with the same OpenAI-compatible Ollama endpoint:

```powershell
.\scripts\python\Measure-QwenLocalSpeed.ps1
```

Use direct Ollama when raw local speed matters. Use LiteLLM when you need
Codex-facing profiles, fallback order, provider routing, quotas, or a single
OpenAI-compatible gateway across local and remote models.

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

## Optional Risk-Adjusted LiteLLM Router

The stable path uses LiteLLM's native router on `127.0.0.1:4000`. An optional
front router can be started on `127.0.0.1:4001` when you want experimental
risk-adjusted dispatching:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  $env:USERPROFILE\.codex\litellm-proxy\start-litellm-proxy.ps1 `
  -EnableRiskRouter
```

The custom router first applies hard limits, then computes a soft risk score on
the remaining candidates:

```text
soft_risk_i =
  wc    * norm(response_cost_i)
+ wttft * norm(ttft_i)
+ wlat  * norm(total_latency_i)
+ wtps  * norm(-tokens_per_second_i)
+ we    * error_rate_i
+ wtok  * token_pressure_i
+ wq    * norm(queue_depth_i)

Pr(i) = softmax(-soft_risk_i / tau)
```

Hard limits keep unavailable deployments out of traffic before scoring. Gemini
`429` free-tier quota responses are cooled down for five minutes, `401`/`403`
auth failures for one hour, and model `404` failures for thirty minutes. Live
in-flight request counts also act as hard limits so a busy local Qwen worker is
not overloaded.

The soft score uses EWMA metrics for TTFT, total latency, tokens/second,
response cost, error rate, token pressure, and queue depth. Streaming requests
update real Time To First Token and generation throughput; non-streaming
requests approximate TTFT as total latency because the buffered upstream
response does not expose the first generated token.

Codex-facing aliases can retry remaining candidates on retryable provider
failures. Direct probes such as `gemini-flash-direct` remain strict so API-key,
model-name, and quota problems are visible instead of hidden by fallback.

Useful diagnostics:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  $env:USERPROFILE\.codex\litellm-proxy\measure-risk-adjusted-dispatch.ps1 `
  -Iterations 5

powershell -NoProfile -ExecutionPolicy Bypass -File `
  $env:USERPROFILE\.codex\litellm-proxy\measure-risk-adjusted-streaming.ps1 `
  -Iterations 3

Invoke-RestMethod http://127.0.0.1:4001/dispatch/metrics
Invoke-RestMethod http://127.0.0.1:4001/dispatch/state
Invoke-RestMethod -Method Post http://127.0.0.1:4001/dispatch/reset
```

Key metrics:

- `ewma_ttft_ms`: streaming Time To First Token.
- `ewma_total_latency_ms`: full request duration.
- `ewma_tokens_per_second`: generation speed after TTFT.
- `ewma_queue_depth` and `in_flight`: current load pressure.
- `hard_limited_remaining_s` and `hard_limit_reason`: temporary exclusions.
- `soft_score_weights`: active scoring weights.

## Routing Policy

Default routing is controlled by `codex-routing-policy.yaml`. Precedence is:

1. CLI flags such as `--provider` and `--codex-provider`
2. environment variables such as `CODEX_ROUTER_PROVIDER`
3. `codex-routing-policy.yaml`
4. built-in safe defaults

Default policy:

```yaml
default_provider: auto
default_codex_provider: auto
open_models_only: false
avoid_openai: false
max_cost_usd: 0.0

task_provider_rules:
  simple: auto
  medium: auto
  complex: openai

fallback_order:
  - litellm
  - standard
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

Start Codex with the standard path:

```powershell
.\scripts\python\codex-cost-routing.cmd
```

Start the LiteLLM proxy only when you want Gemini/API dispatch or a proxy gateway to Qwen:

```powershell
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Start -CodexProvider LiteLLM
codex --profile cost-routing
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Stop
```

Update the local LiteLLM OSS proxy to the latest stable PyPI release:

```powershell
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Update
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Status
```

You can also update while starting the proxy:

```powershell
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Start -CodexProvider LiteLLM -UpdateLiteLLM
```

The launcher automatically bypasses restrictive PowerShell execution policies
for this command only. With no arguments, it opens the normal Codex CLI path:
no LiteLLM proxy, no API-key prompt, no temporary Codex profile.

When `-CodexProvider LiteLLM` is selected, the script:

1. installs the official LiteLLM OSS proxy in `C:\tmp\litellm-oss` when needed;
2. can update the local LiteLLM package with `-Action Update` or `-UpdateLiteLLM`;
3. asks only for optional session keys that are not already set;
4. requires at least `OPENAI_API_KEY`, `GEMINI_API_KEY`, or local Qwen on Ollama;
5. creates a random local `LITELLM_API_KEY` for the proxy session and writes
   only that local proxy key to `%TEMP%\codex-litellm-proxy.key`;
6. starts the LiteLLM proxy in the background;
7. enables the optional Codex `cost-routing` profile;
8. opens Codex with that profile;
9. stops LiteLLM and restores the previous configuration when Codex closes.

### Optional local web key session

If you prefer entering keys in a local page for one work session, start:

```powershell
.\scripts\python\Start-CodexKeySessionWeb.ps1
```

Then open `http://127.0.0.1:8787/`, paste `OPENAI_API_KEY`,
`GEMINI_API_KEY`, or `HF_TOKEN`, and submit the form. Qwen is not managed as an
API provider here: it is only an optional local Ollama fallback. Run
`Start-CodexQwenOllama.ps1` and keep the local Qwen checkbox enabled; no Qwen API
base or API key is accepted by the page. The page starts the LiteLLM proxy on
`http://127.0.0.1:4000/v1` with submitted values only in the proxy process
environment. The keys are not written to disk and the web server suppresses
request logging.

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
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Status
python .\scripts\python\codex_cost_router.py doctor
```

`Status` prints the local LiteLLM version from `C:\tmp\litellm-oss` when it is
installed.

If a browser opened on `http://localhost:4000/health` shows `Unauthorized`,
that is expected: the local proxy is protected by `LITELLM_API_KEY`. The local
test script reads the temporary proxy key automatically after `Start`.

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

## Verification Checklist

Check that the local checkout matches GitHub before changing routing files:

```powershell
git fetch origin
git status -sb
git rev-list --left-right --count main...origin/main
```

The last command should print `0 0`. After edits, run the local validation gate:

```powershell
python -m pytest .\scripts\python\tests\test_codex_cost_router.py .\scripts\python\tests\test_codex_key_session_web.py
python -m ruff check .\scripts\python\codex_cost_router.py .\scripts\python\codex_key_session_web.py .\scripts\python\tests\test_codex_cost_router.py .\scripts\python\tests\test_codex_key_session_web.py
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Status
python .\scripts\python\codex_cost_router.py run --dry-run --codex-provider standard "Verification Codex standard"
```

For local Qwen, verify Ollama and measure throughput:

```powershell
.\scripts\python\Start-CodexQwenOllama.ps1
.\scripts\python\Measure-QwenLocalSpeed.ps1
python .\scripts\python\codex_cost_router.py run --provider qwen --max-output-tokens 20 "Reponds exactement: OK qwen local"
```

For the optional proxy path, start LiteLLM only for Gemini/API dispatch or a
single proxy gateway to local Qwen, then stop it when the session is done:

```powershell
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Start -CodexProvider LiteLLM
.\scripts\python\Test-CodexLiteLLMDispatch.ps1 -Model codex-qwen-local -Call
.\scripts\python\Manage-CodexCostRouting.ps1 -Action Stop
```

The normal final state for daily Codex work is `LiteLLM OSS : arrete` and
`Codex profile : standard`.

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

- `Manage-CodexCostRouting.ps1`: automatic run, persistent start, status, and stop workflow.
- `codex-cost-routing.cmd`: simple Windows launcher.
- `codex_cost_router.py`: prompt optimization and one-shot routing.
- `Invoke-QwenLocal.ps1`: direct Ollama local Qwen call for fast small tasks.
- `Measure-QwenLocalSpeed.ps1`: repeatable local token/s benchmark.
- `codex_key_session_web.py`: local-only web form for session keys.
- `Start-CodexKeySessionWeb.ps1`: PowerShell launcher for the local key page.
- `Test-CodexLiteLLMDispatch.ps1`: local proxy alias and optional call test.
- `start-litellm-proxy.ps1`: local LiteLLM starter with native strategy
  selection and optional risk-router startup.
- `risk_adjusted_router.py`: optional TTFT/tokens-per-second/in-flight-aware
  risk-adjusted front router.
- `measure-risk-adjusted-dispatch.ps1`: non-streaming risk-router benchmark.
- `measure-risk-adjusted-streaming.ps1`: streaming TTFT and throughput probe.
- `codex-routing-policy.yaml`: editable routing policy and fallback order.
- `litellm-cost-routing.yaml`: local LiteLLM OSS OpenAI/Gemini model groups,
  context-window fallbacks, cooldowns, and compatibility aliases.

## Notes

- LiteLLM runs locally and self-hosted.
- The configuration does not enable LiteLLM Cloud or Enterprise features.
- Actual provider billing remains authoritative.
- The router remains optional: stopping it restores the previous Codex
  `config.toml` byte-for-byte.
