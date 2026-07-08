# MCP Server

This directory contains a read-only Python MCP server for browsing and checking
the scripts in this repository.

## Tools

- `list_scripts` lists the available PowerShell, Python, and Bash files.
- `read_script` reads a script using a path relative to `scripts/`.
- `search_scripts` searches for text and returns matching lines.
- `describe_script` returns metadata and a short preview.
- `validate_script` checks syntax without executing the script.
- `list_documentation` lists the Markdown documentation files.
- `read_documentation` reads one Markdown file.
- `get_repository_summary` returns script and documentation statistics.

Python validation uses the standard library parser. Bash and PowerShell
validation use `bash -n` and the PowerShell parser when those programs are
available in `PATH`.

## Installation

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\scripts\python\requirements.txt
```

## Run

```powershell
python .\scripts\python\mcp_server.py
```

The Streamable HTTP endpoint is available at:

```text
http://localhost:8000/mcp
```

To inspect the server:

```powershell
npx -y @modelcontextprotocol/inspector
```

Connect the inspector to `http://localhost:8000/mcp`.

## Codex Cost Router

`codex_cost_router.py` is an optional Windows-friendly wrapper for Codex CLI and
a local LiteLLM OSS proxy. It can clean prompts, compress logs, estimate tokens,
apply budgets, and route one-shot Codex tasks to `codex-light`,
`codex-default`, `codex-long`, or `codex-deep`. The local LiteLLM config
dispatches those aliases across OpenAI and Gemini while keeping API keys in
environment variables. When `HF_TOKEN` is available, it can also route Hugging
Face and multi-provider tasks through the `codex-hf-cheap` and `codex-hf-fast`
LiteLLM aliases, or launch an optional `cost-routing-hf` Codex profile that
points directly at the Hugging Face router. `codex-qwen-local` is available as
a local Ollama fallback through `qwen2.5-coder:3b`.
`codex-routing-policy.yaml` keeps the default provider rules and fallback order
editable without changing Python code.

See [`README_Codex_Cost_Routing.md`](README_Codex_Cost_Routing.md) for setup,
activation, LiteLLM configuration, and usage instructions. For a quick choice
between Standard Codex, LiteLLM, Hugging Face, direct Ollama, and the sovereign
WebUI stack, see [`../../docs/codex-routing-modes.md`](../../docs/codex-routing-modes.md).

To enter OpenAI, Gemini, or Hugging Face keys through a local page for one
session, run `Start-CodexKeySessionWeb.ps1` and open
`http://127.0.0.1:8787/`. Keys are kept in memory for the LiteLLM subprocess
and are not written to disk. Use `Test-CodexLiteLLMDispatch.ps1` for a quick
proxy check, or `healthcheck-litellm-routes.ps1` for a live authenticated check
of the current Codex aliases. Both scripts read the local proxy key from
`LITELLM_API_KEY` or `%TEMP%\codex-litellm-proxy.key` and never print provider
tokens. Add `-Call -Model codex-hf-cheap` after entering a provider key to make
one minimal dispatch request.

## LLM Review Tools

`llm_bias_multi_agent.py` is a provider-agnostic multi-agent manager for
reviewing and revising LLM answers without calling an LLM provider. See
[`README_LLM_Bias_Multi_Agent.md`](README_LLM_Bias_Multi_Agent.md).

## AI-Assisted Security Scan

`ai_server_security_scan.py` performs an authorized, non-destructive server
security scan and can send the structured findings to an OpenAI-compatible AI
API, such as the local LiteLLM proxy, for a defensive remediation plan. It
checks selected TCP ports, basic HTTP security headers, and TLS certificate
metadata. It does not exploit services or brute-force credentials.

Preview a scan without network activity:

```powershell
python .\scripts\python\ai_server_security_scan.py `
  --target example.com `
  --ports 80,443,8080 `
  --dry-run `
  --no-ai
```

Run an authorized scan and write JSON plus Markdown:

```powershell
python .\scripts\python\ai_server_security_scan.py `
  --target example.com `
  --ports 22,80,443,3389 `
  --yes-i-am-authorized `
  --markdown `
  --no-ai
```

Use an AI API through LiteLLM or another OpenAI-compatible endpoint:

```powershell
$env:LITELLM_API_KEY = "local-proxy-key"
python .\scripts\python\ai_server_security_scan.py `
  --target example.com `
  --ports 22,80,443 `
  --yes-i-am-authorized `
  --markdown `
  --ai-endpoint http://127.0.0.1:4000/v1 `
  --ai-model codex-default `
  --ai-api-key-env LITELLM_API_KEY
```

## Client Cloud EU Audit

Before installing the LiteLLM/Codex routing stack for a client on Azure or AWS,
use [`audit/CLIENT_CLOUD_EU_AUDIT.md`](audit/CLIENT_CLOUD_EU_AUDIT.md). It
adds a 1-day audit flow for EU-region deployment, GDPR/RGPD triage, AI Act
classification, NIS2/DORA relevance, secret management, redacted logging,
adaptive-routing evidence, cost measurement, and avoided `429` tracking.

## Client Cost Savings Calculator

`client_cost_savings.py` calculates monthly savings and avoided `429` errors
from an editable JSON assumptions file. Prices are not hardcoded in the script,
so OVHcloud, Hetzner, AWS, Azure, and model-provider price changes can be
handled by updating the JSON and rerunning the same formula.

```powershell
python .\scripts\python\client_cost_savings.py `
  --input .\docs\smb-llm-pilot\cost-savings-input.example.json `
  --format markdown
```

See
[`../../docs/client-cost-savings-calculator.md`](../../docs/client-cost-savings-calculator.md)
for the client-facing calculation method.
