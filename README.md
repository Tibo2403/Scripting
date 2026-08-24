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
| `deploy/` | **Experimental** | Static validation exists; no end-to-end Akash deployment test |
| `openclaw-akash-dual-agents/` | **Experimental** | Shell syntax only; external integrations are not tested end to end |
| `openclaw-inkling-akash/` | **Experimental** | Shell syntax only; provider and deployment are not tested end to end |
| `pra/` | **Experimental** | Recovery connectors are placeholders and require a real exercise |
| `tokenized_llm_finance/` | **Experimental** | Contracts are unaudited and Foundry is not yet run in CI |

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
|-- deploy/                   # Experimental deployment configurations
|-- examples/                 # Safe placeholders and demonstration inputs
|-- litellm_scaleway_dispatching/ # Usable, unit-tested provider integration
|-- openclaw-*/               # Experimental OpenClaw deployment prototypes
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

### Codex workspace audit

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 -ProjectPath . -Fix -Validate
```

The workspace doctor audits a project before a Codex CLI session and can maintain a generated section in `AGENTS.md`. See [`docs/codex-workspace-doctor.md`](docs/codex-workspace-doctor.md).

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
- [`docs/codex-routing-modes.md`](docs/codex-routing-modes.md)
- [`scripts/python/PRODUCTION_SECURITY_GOVERNANCE.md`](scripts/python/PRODUCTION_SECURITY_GOVERNANCE.md)

Experimental routers should remain bound to `127.0.0.1` unless authentication and TLS are added.

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
