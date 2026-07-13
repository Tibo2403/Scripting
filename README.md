# Scripting Toolkit

[![Script Validation](https://github.com/Tibo2403/Scripting/actions/workflows/script-validation.yml/badge.svg)](https://github.com/Tibo2403/Scripting/actions/workflows/script-validation.yml)

Collection of PowerShell, Bash, and Python scripts for system administration, security checks, Microsoft 365 operations, Linux dependency checks, MCP integrations, Codex/LiteLLM routing experiments, and authorized lab or pentest workflows.

## Legal Notice

Use the pentest scripts only on systems where you have explicit written authorization. Unauthorized scanning, exploitation, credential access, or data transfer can be illegal and harmful.

The scripts in `scripts/linux/pentest_*.sh`, `scan_wifi.sh`, and `stealth_post.sh` are intended for controlled labs, training environments, or sanctioned security assessments.

For client deployments of self-hosted AI, LiteLLM, Ollama, Open WebUI, or LLM gateways, complete the pre-installation audit checklist before touching the customer environment: [`docs/client-preinstallation-audit.md`](docs/client-preinstallation-audit.md).

## Repository Structure

```text
.
|-- .github/workflows/
|   |-- ai-refactor.yml
|   `-- script-validation.yml
|-- docs/
|   |-- client-preinstallation-audit.md
|   |-- client-cost-savings-calculator.md
|   |-- codex-routing-modes.md
|   |-- codex-workspace-doctor.md
|   |-- compatibility-matrix.md
|   |-- demo-media.md
|   |-- issue-backlog.md
|   |-- portfolio.md
|   `-- self-hosted-llm.md
|-- examples/
|-- scripts/
|   |-- bash/
|   |   |-- install_ia_souveraine.sh
|   |   `-- install_llm_microservice.sh
|   |-- linux/
|   |   |-- check_dependencies.sh
|   |   |-- dependencies.conf
|   |   |-- install_ollama_private_server.sh
|   |   |-- pentest_discovery.sh
|   |   |-- pentest_exploitation.sh
|   |   |-- pentest_verification.sh
|   |   |-- README.md
|   |   |-- scan_wifi.sh
|   |   |-- setup_api.sh
|   |   `-- stealth_post.sh
|   |-- powershell/
|   |-- python/
|   |   |-- README.md
|   |   |-- README_Codex_Cost_Routing.md
|   |   |-- README_LLM_Bias_Multi_Agent.md
|   |   |-- adaptive_token_pressure_router.py
|   |   |-- codex-cost-routing.cmd
|   |   |-- codex-routing-policy.yaml
|   |   |-- codex_cost_profiles.py
|   |   |-- codex_cost_router.py
|   |   |-- codex_key_session_web.py
|   |   |-- healthcheck-litellm-routes.ps1
|   |   |-- litellm-cost-routing.yaml
|   |   |-- mcp_server.py
|   |   |-- requirements.txt
|   |   |-- risk_adjusted_router.py
|   |   |-- start_litellm_proxy.py
|   |   |-- Test-CodexLiteLLMDispatch.ps1
|   |   `-- Switch-CodexLiteLLM.ps1
|   `-- tests/
|       |-- Test-Optimize-CodexWorkspace.ps1
|       |-- Test-Switch-CodexLiteLLM.ps1
|       `-- test-linux-safety.sh
|-- AGENTS.md
|-- CHANGELOG.md
|-- LICENSE
|-- PSScriptAnalyzerSettings.psd1
|-- README.md
`-- targets.txt
```

`targets.txt` contains example targets used by the pentest scripts. Keep it limited to systems that you are allowed to test.

See `docs/compatibility-matrix.md` for OS support, privilege requirements, dependencies, risk level, and dry-run availability per script.

Portfolio, client-readiness, and maintenance docs:

- `docs/portfolio.md` explains the repository in recruiter/client terms.
- `docs/client-preinstallation-audit.md` is the standard client audit checklist to complete before installing a self-hosted AI, LiteLLM, Ollama, Open WebUI, or LLM gateway stack in a Belgian customer environment.
- `docs/client-cost-savings-calculator.md` provides a client-facing cost
  savings and avoided-429 calculation document for the pilot.
- `docs/demo-media.md` lists screenshots and GIFs to capture.
- `docs/issue-backlog.md` contains ready-to-create GitHub issues.
- `docs/codex-workspace-doctor.md` documents `Optimize-CodexWorkspace.ps1`.
- `docs/self-hosted-llm.md` documents the local Open WebUI stack and the
  LiteLLM/Ollama microservice for Linux VMs, Docker clouds, and Akash Network.
- `docs/compute-cost-arbitrage.md` documents the dependency-free calculator for
  owned GPU electricity, rented compute, API token pricing, and quality floors.
- `docs/smb-llm-self-hosting-one-day.md` and `docs/smb-llm-pilot/` provide a
  one-day SMB LiteLLM/Ollama setup runbook with fill-in pilot templates.
- `docs/codex-routing-modes.md` compares direct Codex, LiteLLM proxy, and
  risk-adjusted router modes.
- `CHANGELOG.md` tracks release notes.

## Temporary OpenClaw Orchestration

OpenClaw can be used during the 1 Day Implementation setup only to coordinate
the workflow: split tasks, call Codex for implementation, run validation
scripts, check test results, and prepare the final report. It is documented in
[`OPENCLAW_TEMP_ORCHESTRATOR.md`](OPENCLAW_TEMP_ORCHESTRATOR.md), with prompts
and placeholders under [`1-day-implementation/`](1-day-implementation/).

After installation, the project must remain usable without OpenClaw. Do not add
OpenClaw as a permanent runtime dependency or architecture requirement.

Fast path without Codex:

```powershell
.\1-day-implementation\scripts\audit_repo.ps1
.\1-day-implementation\scripts\install.ps1 -NoCodex
.\1-day-implementation\scripts\run_tests.ps1
.\1-day-implementation\scripts\validate_installation.ps1
```

Deployment modes can be selected without making OpenClaw permanent:

- `Local` for the quickest manual host setup.
- `DockerCompose` for the portable app stack in [`docker-compose.yml`](docker-compose.yml).
- `Ansible` for existing OVH, Hetzner, or customer Linux servers in [`ansible/`](ansible/).
- `AWS` for automatic cloud provisioning notes in [`infra/aws/`](infra/aws/).
- `Azure` for automatic cloud provisioning notes in [`infra/azure/`](infra/azure/).

Example:

```powershell
.\1-day-implementation\scripts\install.ps1 -Mode DockerCompose -NoCodex
```

## Prerequisites

- PowerShell 5.1+ or PowerShell 7+ for Windows scripts.
- Linux shell tools for Bash scripts.
- Python 3.10+ for Python utilities.
- Python dependencies from `scripts/python/requirements.txt` for MCP, YAML policy parsing, and Python tests.
- Optional tools depending on the script: `nmap`, `gvm-cli`, `curl`, `gpg`, `pwsh`, Docker, Ollama, Codex CLI, and LiteLLM.
- Optional PowerShell modules: Hyper-V, ExchangeOnlineManagement, MicrosoftTeams, PnP.PowerShell.
- Administrator or root privileges for scripts that manage services, users, VMs, network scans, or security settings.

## Quick Checks

Validate PowerShell syntax:

```powershell
.\scripts\powershell\Test-ScriptSyntax.ps1 -Path .\scripts
```

Run PowerShell static analysis:

```powershell
Install-Module -Name PSScriptAnalyzer -Scope CurrentUser
Invoke-ScriptAnalyzer -Path .\scripts -Recurse -Settings .\PSScriptAnalyzerSettings.psd1
```

Validate Bash syntax from Linux, WSL, Git Bash, or CI:

```bash
find scripts -name "*.sh" -print0 | xargs -0 -n1 bash -n
```

Run Bash static analysis:

```bash
find scripts -name "*.sh" -print0 | xargs -0 shellcheck --severity=error
```

Validate Python syntax and tests:

```powershell
python -m pip install -r .\scripts\python\requirements.txt
Get-ChildItem .\scripts\python -Filter *.py -Recurse | ForEach-Object { python -m py_compile $_.FullName }
python -m unittest discover -s .\scripts\python\tests -v
```

Check Linux dependencies:

```bash
bash scripts/linux/check_dependencies.sh
```

Run the Linux safety smoke tests:

```bash
bash scripts/tests/test-linux-safety.sh
```

Run the Codex Workspace Doctor smoke test:

```powershell
.\scripts\tests\Test-Optimize-CodexWorkspace.ps1
```

Run the LiteLLM routing smoke test:

```powershell
.\scripts\tests\Test-Switch-CodexLiteLLM.ps1
```

## PowerShell Examples

```powershell
.\scripts\powershell\Get-SystemInfo.ps1
.\scripts\powershell\ManageServices.ps1 -Action status -ServiceName spooler
.\scripts\powershell\Optimize-CodexWorkspace.ps1 -ProjectPath . -Fix -Validate
.\scripts\powershell\VMManagement.ps1 -Action list
.\scripts\powershell\TeamsManagement.ps1 -Action list
.\scripts\powershell\ExchangeOnlineManagement.ps1 -Action list
.\scripts\powershell\SecurityCheck.ps1
```

`ManageServices.ps1` and `UserManagement.ps1` require an elevated PowerShell session for privileged actions.

`Optimize-CodexWorkspace.ps1` audits a project before a Codex CLI session and can maintain a generated section in `AGENTS.md`. See [`docs/codex-workspace-doctor.md`](docs/codex-workspace-doctor.md).

## Linux Examples

```bash
bash scripts/bash/install_ia_souveraine.sh --dry-run --skip-model
bash scripts/bash/install_llm_microservice.sh --dry-run \
  --master-key 'sk-example-key-1234' \
  --with-openclaw
bash scripts/linux/check_dependencies.sh
bash scripts/linux/pentest_discovery.sh --dry-run --yes-i-am-authorized
bash scripts/linux/pentest_verification.sh --dry-run --yes-i-am-authorized
bash scripts/linux/pentest_exploitation.sh --dry-run --yes-i-am-authorized
```

Compatibility wrappers are also available at `scripts/pentest_discovery.sh`, `scripts/pentest_verification.sh`, and `scripts/pentest_exploitation.sh`. They forward arguments to the guarded implementations in `scripts/linux/`.

Authorized pentest discovery can be run with explicit target, output, pacing, and parallelism controls:

```bash
bash scripts/linux/pentest_discovery.sh \
  --targets targets.txt \
  --outdir pentest_results/lab-run \
  --jobs 2 \
  --rate-limit 1 \
  --yes-i-am-authorized
```

The discovery script writes `discovery_summary.tsv` in the run directory and updates `pentest_results/latest` when the platform allows symlinks. Verification uses that latest run by default, preserves the original target values from the summary, can target a subset of hosts, and can skip heavier integrations when the lab does not have OpenVAS or Metasploit installed.

For `stealth_post.sh`, pass credentials through environment variables or a local config file that is never committed:

```bash
export FTP_USER="user"
export FTP_PASS="password"
export FTP_HOST="example.com"
export FTP_PATH="uploads/sysinfo.txt.gpg"
export GPG_PASSPHRASE="secret_passphrase"
bash scripts/linux/stealth_post.sh --dry-run --yes-i-am-authorized
```

Sensitive Linux scripts require either an interactive `AUTHORIZED` confirmation or the explicit `--yes-i-am-authorized` flag. Use `--dry-run` first to review planned scans, captures, or transfers.

Use the safe placeholders in `examples/` for lab demos and documentation. Do not commit real targets, credentials, tenant identifiers, scan output, packet captures, or customer data.

Before running a self-hosted AI installation for a customer, complete [`docs/client-preinstallation-audit.md`](docs/client-preinstallation-audit.md). The checklist helps confirm scope, RGPD constraints, security controls, infrastructure readiness, monitoring, rollback, and the final go/no-go decision.

`install_ia_souveraine.sh` starts a local Open WebUI + Ollama stack in Docker. It keeps model and WebUI data in Docker volumes and supports conservative dry-run checks before installation. See [`docs/self-hosted-llm.md`](docs/self-hosted-llm.md) for usage, persistence, GPU behavior, and troubleshooting.

`install_llm_microservice.sh` deploys a persistent Ollama model behind an
authenticated LiteLLM/OpenAI-compatible API on a Debian/Ubuntu VM, any Docker
cloud, or Akash Network. The optional `--with-openclaw` output configures
OpenClaw agents as clients of the gateway, including a strict no-fallback agent
profile. It binds to localhost by default; use `--host 0.0.0.0` only with an
appropriate firewall and TLS reverse proxy. See
[`docs/self-hosted-llm.md`](docs/self-hosted-llm.md#cloud-litellm-microservice).

`compute_cost_arbitrage.py` compares owned hardware, rented GPU compute such as
an accepted Akash bid, and hosted LLM APIs. It includes kWh, PUE, hardware
amortization, capacity, and a minimum quality score, and returns the selected
LiteLLM alias without changing live routes. Optional CSV history and daily or
ISO-week trend exports track average, minimum, maximum, and period-over-period
cost changes. See
[`docs/compute-cost-arbitrage.md`](docs/compute-cost-arbitrage.md).

## Python Tools

The read-only Python MCP server exposes tools to list, search, inspect, and validate scripts without executing them. It can also browse documentation and return a repository summary:

```powershell
pip install -r .\scripts\python\requirements.txt
python .\scripts\python\mcp_server.py
```

Connect an MCP client to `http://localhost:8000/mcp`. See [`scripts/python/README.md`](scripts/python/README.md) for setup and inspector instructions.

`scripts/python/ai_server_security_scan.py` provides an authorized,
non-destructive server security scan with optional AI-assisted remediation via
an OpenAI-compatible API such as LiteLLM. Use `--dry-run` first and
`--yes-i-am-authorized` before any live scan. The canonical architecture and
usage guide is [`docs/security-scanning.md`](docs/security-scanning.md).

The optional Codex cost router in `scripts/python/codex_cost_router.py` can compress one-shot prompts and route them through a self-hosted LiteLLM OSS proxy. The surrounding tools manage session keys, local proxy status, route health checks, and adaptive token-pressure dispatch experiments. See [`scripts/python/README_Codex_Cost_Routing.md`](scripts/python/README_Codex_Cost_Routing.md), [`scripts/python/PRODUCTION_SECURITY_GOVERNANCE.md`](scripts/python/PRODUCTION_SECURITY_GOVERNANCE.md), and the short mode chooser in [`docs/codex-routing-modes.md`](docs/codex-routing-modes.md).

For a one-day SMB implementation plan that combines the LiteLLM proxy, local
Ollama fallback, adaptive routing, measurements, security checks, and operating
handoff, see [`docs/smb-llm-self-hosting-one-day.md`](docs/smb-llm-self-hosting-one-day.md).
For the client cost report, use
[`docs/client-cost-savings-calculator.md`](docs/client-cost-savings-calculator.md)
with the metrics template in
[`docs/smb-llm-pilot/LLM_METRICS.md`](docs/smb-llm-pilot/LLM_METRICS.md).

The optional risk-adjusted router in `scripts/python/risk_adjusted_router.py` uses the LiteLLM-independent scoring helper in `scripts/python/adaptive_token_pressure_router.py`. It should stay bound to `127.0.0.1` and should not be exposed directly on a network without authentication and TLS.

The optional LLM review tool in `scripts/python/llm_bias_multi_agent.py` provides deterministic first-pass bias, fairness, and safeguard checks. See [`scripts/python/README_LLM_Bias_Multi_Agent.md`](scripts/python/README_LLM_Bias_Multi_Agent.md).

## CI

The `script-validation.yml` workflow checks:

- PowerShell syntax for every `.ps1`, `.psm1`, and `.psd1` file.
- PSScriptAnalyzer error-level findings using `PSScriptAnalyzerSettings.psd1`.
- Bash syntax for every Linux shell script.
- ShellCheck error-level findings.
- Linux `--help` and `--dry-run` safety smoke tests.
- Python dependencies, syntax for every Python file under `scripts/python`, and Python unit tests.
- Dedicated script smoke tests in `scripts/tests/`.

The AI refactor workflow is manual-only to avoid surprise API usage and automatic hourly write attempts.
When a patch is generated, it must pass compile checks, Python unit discovery,
PowerShell syntax validation, PSScriptAnalyzer, Bash syntax checks, and
ShellCheck before a pull request is opened.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
