# Guides d’exploitation et de validation

Exécutez les commandes depuis la racine du dépôt.

### OpenClaw deployment profiles

- [Dual agents](../openclaw-akash-dual-agents/README.md): two agents for read-only repository review, with persistent repositories and Telegram pairing.
- [Inkling gateway](../openclaw-inkling-akash/README.md): a private gateway with a configurable OpenAI-compatible provider.

Both profiles build from the repository root and require their documented environment variables. Start with the linked guide to configure secrets, build the image and run the first manual check. Akash deployment and provider calls require separate operator validation.

### Codex workspace audit

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 -ProjectPath . -Fix -Validate
```

The workspace doctor audits a project before a Codex CLI session and can maintain a generated section in `AGENTS.md`. See [`docs/codex-workspace-doctor.md`](codex-workspace-doctor.md).

### Grok coding agent on GitHub

The manual `Grok coder` workflow runs Grok Build on an ephemeral GitHub-hosted runner and opens a
draft pull request with its changes. It does not require Akash, MCP or an external review plugin.

1. Create an xAI API key and save it as the repository Actions secret `XAI_API_KEY`.
2. In **Settings > Actions > General**, allow GitHub Actions to create pull requests.
3. Open **Actions > Grok coder (manual) > Run workflow**.
4. Enter a focused coding task and start the workflow.
5. Review the generated draft pull request and its standard CI checks before merging.

The agent cannot merge directly. Its prompt also prevents changes to GitHub workflow files; make
those changes manually when required.

### Private AI stack

```bash
bash scripts/bash/install_ia_souveraine.sh --dry-run --skip-model
```

The installer prepares a local Open WebUI and Ollama stack in Docker with conservative checks and persistent volumes. See [`docs/self-hosted-llm.md`](self-hosted-llm.md).

### Read-only MCP server

```bash
pip install -r scripts/python/requirements.txt
python scripts/python/mcp_server.py
```

Connect an MCP client to `http://localhost:8000/mcp`. The server can list, search, inspect and validate repository scripts without executing them.

### Budget-aware LLM routing

The Python tooling includes experiments for Codex/LiteLLM routing, local route health checks and risk-adjusted dispatch. Start with:

- [`scripts/python/README_Codex_Cost_Routing.md`](../scripts/python/README_Codex_Cost_Routing.md)
- [`scripts/python/README_Astra_Switch.md`](../scripts/python/README_Astra_Switch.md): Windows launcher for selecting and restoring a dedicated local Astra route; requires the existing LiteLLM proxy and an API key.
- [`docs/codex-routing-modes.md`](codex-routing-modes.md)
- [`scripts/python/PRODUCTION_SECURITY_GOVERNANCE.md`](../scripts/python/PRODUCTION_SECURITY_GOVERNANCE.md)

Experimental routers should remain bound to `127.0.0.1` unless authentication and TLS are added.

### Inkling gateway in GitHub Codespaces

The repository devcontainer provides a private LiteLLM gateway for the official
Vercel Inkling endpoint. Add `INKLING_API_KEY` and `LITELLM_MASTER_KEY` as
Codespaces repository secrets, then create or rebuild the Codespace. Port 4000
is forwarded privately and the OpenAI-compatible model name exposed to clients
is `inkling`.

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"inkling","messages":[{"role":"user","content":"Hello"}]}'
```

If the Codespace was created before the secrets were configured, start the
gateway explicitly after rebuilding it:

```bash
bash .devcontainer/start-inkling-gateway.sh
```

## Validation

### PowerShell

```powershell
.\scripts\powershell\Test-ScriptSyntax.ps1 -Path .\scripts
Install-Module -Name PSScriptAnalyzer -Scope CurrentUser
Invoke-ScriptAnalyzer -Path .\scripts -Recurse -Settings .\PSScriptAnalyzerSettings.psd1
.\scripts\tests\Test-Optimize-CodexWorkspace.ps1
.\scripts\tests\Test-Switch-CodexLiteLLM.ps1
```

### Bash

```bash
find scripts -name "*.sh" -print0 | xargs -0 -n1 bash -n
find scripts -name "*.sh" -print0 | xargs -0 shellcheck --severity=error
bash scripts/tests/test-linux-safety.sh
```

### Python

```bash
python -m pip install -r scripts/python/requirements.txt
find scripts/python -name "*.py" -print0 | xargs -0 -n1 python -m py_compile
python -m unittest discover -s scripts/python/tests -v
```

The usable-project workflow performs PowerShell syntax checks, PSScriptAnalyzer, Bash syntax checks,
ShellCheck, Linux safety smoke tests, Python compilation and unit tests. A separate experimental
workflow runs the checks currently available for prototypes; a green experimental check is not a
promotion to usable and its intentionally missing coverage remains listed in the maturity catalog.
