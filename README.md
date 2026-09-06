# Scripting Toolkit

[![Usable Projects Validation](https://github.com/Tibo2403/Scripting/actions/workflows/script-validation.yml/badge.svg)](https://github.com/Tibo2403/Scripting/actions/workflows/script-validation.yml)

**Monorepo d'automatisation PowerShell, Bash et Python, avec une separation explicite entre les outils utilisables et les prototypes experimentaux.**

Use this repository to audit a Codex workspace, deploy a private Ollama/Open WebUI stack, validate scripts across operating systems, operate Microsoft 365 services, or experiment with budget-aware LLM routing.

## Maturity at a glance

**Usable** means documented and covered by repeatable CI checks for its stated scope. It does not
mean certified for unattended production. **Experimental** means interfaces or guarantees are still
incomplete and real secrets, critical systems and real financial value must not be used.

| Project directory | Maturity | Current evidence or gap |
|---|---|---|
| `scripts/` | **Usable** | PowerShell, Bash and Python checks run in CI |
| `litellm_scaleway_dispatching/` | **Usable** | Provider calls are mocked; retry and fallback are unit tested |
| `deploy/` | **Usable** | Security invariants, runtime failures and Docker build definitions run in CI; Akash deployment stays operator-controlled |
| `openclaw-akash-dual-agents/` | **Usable** | Read-only code review; configuration and failure tests, dedicated Docker CI |
| `openclaw-inkling-akash/` | **Usable** | Configurable private gateway; configuration and failure tests, dedicated Docker CI |
| `pra/` | **Experimental** | Recovery connectors are placeholders and require a real exercise |
| `tokenized_llm_finance/` | **Experimental** | Contracts are unaudited and Foundry is not yet run in CI |

The two OpenClaw profile promotions require a green [dedicated CI run](https://github.com/Tibo2403/Scripting/actions/workflows/openclaw-deployments.yml) before merge. Local configuration tests and the pinned OpenClaw schema passed. Docker Linux 29.6.1 and `docker run --rm hello-world` were verified on 2026-09-06; builds of the project images and external integrations remain unverified. See [validation evidence](scripts/openclaw/VALIDATION.md).

### Isolated boundary for tokenized finance

`tokenized_llm_finance/` is not an execution dependency of the usable scripting toolkit. Its
mandatory [project boundary](tokenized_llm_finance/BOUNDARIES.md) excludes Treasury reserve
management, leverage/repo, cross-project imports and any claim to stabilize US long-term rates.
Any such activity belongs in a separately governed and reviewed project.

The machine-readable source of truth is [`project-maturity.toml`](project-maturity.toml). Promotion
criteria and the meaning of each level are defined in
[`docs/project-maturity.md`](docs/project-maturity.md).

## Try it in under 5 minutes

Clone the repository, then run one of these safe entry points:

```powershell
# Audit and validate a developer workspace
.\scripts\powershell\Optimize-CodexWorkspace.ps1 -ProjectPath . -Validate

# Inspect local system information
.\scripts\powershell\Get-SystemInfo.ps1
```

```bash
# Preview a private AI stack without changing the host
bash scripts/bash/install_ia_souveraine.sh --dry-run --skip-model

# Check Linux dependencies and repository safety controls
bash scripts/linux/check_dependencies.sh
bash scripts/tests/test-linux-safety.sh
```

```bash
# Start the read-only MCP server for script discovery and inspection
pip install -r scripts/python/requirements.txt
python scripts/python/mcp_server.py
```

## What is included

| Area | Examples |
|---|---|
| AI infrastructure | Ollama, Open WebUI, LiteLLM, model routing and cost controls |
| Developer tooling | Codex workspace audits, MCP inspection, validation helpers |
| System administration | Services, users, VMs, Linux dependencies and host diagnostics |
| Microsoft 365 | Teams, Exchange Online and PnP PowerShell operations |
| Security labs | Guarded discovery, verification and exploitation workflows for authorized environments |
| Quality engineering | PowerShell, Bash and Python validation through GitHub Actions |

## Repository map

```text
.
|-- .github/workflows/        # Script validation and manual AI-assisted refactoring
|-- docs/                     # Operations, compatibility and client-readiness guidance
|-- deploy/                   # Usable, tested Akash OpenClaw deployment configuration
|-- examples/                 # Safe placeholders and demonstration inputs
|-- litellm_scaleway_dispatching/ # Usable, unit-tested provider integration
|-- openclaw-*/               # OpenClaw deployment profiles; promotion pending CI
|-- pra/                      # Experimental recovery-plan orchestrator
|-- scripts/
|   |-- bash/                 # AI infrastructure installers
|   |-- linux/                # Linux administration and authorized lab workflows
|   |-- powershell/           # Windows, Microsoft 365 and workspace automation
|   |-- python/               # MCP tools and LLM routing experiments
|   `-- tests/                # Safety and smoke tests
|-- tokenized_llm_finance/    # Experimental Python/Solidity finance prototype
|-- AGENTS.md
|-- CHANGELOG.md
|-- CONTRIBUTING.md
|-- LICENSE
|-- project-maturity.toml
`-- README.md
```

See [`docs/compatibility-matrix.md`](docs/compatibility-matrix.md) for operating-system support, required privileges, dependencies, risk level and dry-run availability.

## Core workflows

### OpenClaw deployment profiles

- [Dual agents](openclaw-akash-dual-agents/README.md): two agents for read-only repository review, with persistent repositories and Telegram pairing.
- [Inkling gateway](openclaw-inkling-akash/README.md): a private gateway with a configurable OpenAI-compatible provider.

Both profiles build from the repository root and require their documented environment variables. Start with the linked guide to configure secrets, build the image and run the first manual check. Akash deployment and provider calls require separate operator validation.

### Codex workspace audit

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 -ProjectPath . -Fix -Validate
```

The workspace doctor audits a project before a Codex CLI session and can maintain a generated section in `AGENTS.md`. See [`docs/codex-workspace-doctor.md`](docs/codex-workspace-doctor.md).

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

The installer prepares a local Open WebUI and Ollama stack in Docker with conservative checks and persistent volumes. See [`docs/self-hosted-llm.md`](docs/self-hosted-llm.md).

### Read-only MCP server

```bash
pip install -r scripts/python/requirements.txt
python scripts/python/mcp_server.py
```

Connect an MCP client to `http://localhost:8000/mcp`. The server can list, search, inspect and validate repository scripts without executing them.

### Budget-aware LLM routing

The Python tooling includes experiments for Codex/LiteLLM routing, local route health checks and risk-adjusted dispatch. Start with:

- [`scripts/python/README_Codex_Cost_Routing.md`](scripts/python/README_Codex_Cost_Routing.md)
- [`scripts/python/README_Astra_Switch.md`](scripts/python/README_Astra_Switch.md): Windows launcher for selecting and restoring a dedicated local Astra route; requires the existing LiteLLM proxy and an API key.
- [`docs/codex-routing-modes.md`](docs/codex-routing-modes.md)
- [`scripts/python/PRODUCTION_SECURITY_GOVERNANCE.md`](scripts/python/PRODUCTION_SECURITY_GOVERNANCE.md)

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

## Authorized security use only

Use security and pentest scripts only on systems where you have explicit written authorization. Unauthorized scanning, exploitation, credential access or data transfer can be illegal and harmful.

Sensitive workflows require an interactive `AUTHORIZED` confirmation or the explicit `--yes-i-am-authorized` flag. Always use `--dry-run` first.

Do not commit real targets, credentials, API keys, tenant identifiers, customer data, scan output, packet captures or encrypted payloads. Use environment variables and local configuration excluded from Git.

## Documentation

- [`docs/portfolio.md`](docs/portfolio.md): recruiter and client-facing project overview
- [`docs/client-preinstallation-audit.md`](docs/client-preinstallation-audit.md): customer deployment and RGPD readiness checklist
- [`docs/demo-media.md`](docs/demo-media.md): screenshots and GIFs to capture
- [`docs/issue-backlog.md`](docs/issue-backlog.md): contribution-ready issue ideas
- [`CHANGELOG.md`](CHANGELOG.md): release history

## Contributing

Contributions are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md), keep changes focused, add or update tests, and preserve authorization and dry-run safeguards for sensitive scripts.

## Suggested GitHub topics

`powershell` · `bash` · `python` · `automation` · `devops` · `system-administration` · `security-tools` · `litellm` · `ollama` · `ai-infrastructure`

## License

Licensed under the [MIT License](LICENSE).
