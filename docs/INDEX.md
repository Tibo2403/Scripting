# Index des scripts

> Généré par `scripts/python/generate_index.py` — ne pas éditer à la main.

94 scripts dans 16 catégories.

## Sommaire

- [(racine)](#racine) (3)
- [bash](#bash) (2)
- [deploy / akash-openclaw-doc-agent](#deploy--akash-openclaw-doc-agent) (2)
- [linux](#linux) (8)
- [litellm_scaleway_dispatching](#litellm_scaleway_dispatching) (2)
- [openclaw-akash-dual-agents](#openclaw-akash-dual-agents) (2)
- [openclaw-inkling-akash](#openclaw-inkling-akash) (2)
- [powershell](#powershell) (12)
- [pra](#pra) (2)
- [python](#python) (29)
- [python / openclaw_crewai_admin](#python--openclaw_crewai_admin) (7)
- [tokenized_llm_finance / contracts](#tokenized_llm_finance--contracts) (7)
- [tokenized_llm_finance / python](#tokenized_llm_finance--python) (9)
- [tokenized_llm_finance / script](#tokenized_llm_finance--script) (2)
- [tokenized_llm_finance / test](#tokenized_llm_finance--test) (2)
- [tools](#tools) (3)

## (racine)

| Script | Langage | Description |
| --- | --- | --- |
| [`pentest_discovery.sh`](../scripts/pentest_discovery.sh) | Bash |  |
| [`pentest_exploitation.sh`](../scripts/pentest_exploitation.sh) | Bash |  |
| [`pentest_verification.sh`](../scripts/pentest_verification.sh) | Bash |  |

## bash

| Script | Langage | Description |
| --- | --- | --- |
| [`deploy_inkling_akash.sh`](../scripts/bash/deploy_inkling_akash.sh) | Bash |  |
| [`install_ia_souveraine.sh`](../scripts/bash/install_ia_souveraine.sh) | Bash |  |

## deploy / akash-openclaw-doc-agent

| Script | Langage | Description |
| --- | --- | --- |
| [`run-ollama.sh`](../deploy/akash-openclaw-doc-agent/runtime/run-ollama.sh) | Bash |  |
| [`validate.py`](../deploy/akash-openclaw-doc-agent/scripts/validate.py) | Python | Validate the security invariants of the Akash documentation agent. |

## linux

| Script | Langage | Description |
| --- | --- | --- |
| [`check_dependencies.sh`](../scripts/linux/check_dependencies.sh) | Bash | check_dependencies.sh - Vérifie la présence des outils requis pour les scripts du dépôt |
| [`install_ollama_private_server.sh`](../scripts/linux/install_ollama_private_server.sh) | Bash |  |
| [`pentest_discovery.sh`](../scripts/linux/pentest_discovery.sh) | Bash | pentest_discovery.sh - discovery phase for authorized assessments. |
| [`pentest_exploitation.sh`](../scripts/linux/pentest_exploitation.sh) | Bash | pentest_exploitation.sh - suggestion generation for authorized assessments. |
| [`pentest_verification.sh`](../scripts/linux/pentest_verification.sh) | Bash | pentest_verification.sh - vulnerability verification for authorized assessments. |
| [`scan_wifi.sh`](../scripts/linux/scan_wifi.sh) | Bash | scan_wifi.sh - WPA handshake capture helper for authorized Wi-Fi tests. |
| [`setup_api.sh`](../scripts/linux/setup_api.sh) | Bash | setup_api.sh - Installe un environnement Python pour une API |
| [`stealth_post.sh`](../scripts/linux/stealth_post.sh) | Bash | stealth_post.sh - encrypted FTPS transfer helper for authorized assessments. |

## litellm_scaleway_dispatching

| Script | Langage | Description |
| --- | --- | --- |
| [`__init__.py`](../litellm_scaleway_dispatching/__init__.py) | Python | LiteLLM Scaleway dispatching package. |
| [`scaleway_glm_dispatcher.py`](../litellm_scaleway_dispatching/scaleway_glm_dispatcher.py) | Python | Production-oriented Scaleway GLM dispatching helpers for LiteLLM. |

## openclaw-akash-dual-agents

| Script | Langage | Description |
| --- | --- | --- |
| [`entrypoint.sh`](../openclaw-akash-dual-agents/scripts/entrypoint.sh) | Bash |  |
| [`validate-models.sh`](../openclaw-akash-dual-agents/scripts/validate-models.sh) | Bash |  |

## openclaw-inkling-akash

| Script | Langage | Description |
| --- | --- | --- |
| [`entrypoint.sh`](../openclaw-inkling-akash/entrypoint.sh) | Bash |  |
| [`render-deploy.sh`](../openclaw-inkling-akash/render-deploy.sh) | Bash |  |

## powershell

| Script | Langage | Description |
| --- | --- | --- |
| [`DiskUsageReport.ps1`](../scripts/powershell/DiskUsageReport.ps1) | PowerShell | Generates a disk usage report for local drives and optionally |
| [`ExchangeOnlineManagement.ps1`](../scripts/powershell/ExchangeOnlineManagement.ps1) | PowerShell | Manages Exchange Online mailboxes. |
| [`Get-SystemInfo.ps1`](../scripts/powershell/Get-SystemInfo.ps1) | PowerShell | Displays detailed system information for the local computer. |
| [`LinkCrawler.ps1`](../scripts/powershell/LinkCrawler.ps1) | PowerShell | Crawls a website to verify the status of internal and external links. |
| [`ManageServices.ps1`](../scripts/powershell/ManageServices.ps1) | PowerShell | Starts, stops, restarts or checks the status of a Windows service. |
| [`Optimize-CodexWorkspace.ps1`](../scripts/powershell/Optimize-CodexWorkspace.ps1) | PowerShell | Audits a repository before launching Codex CLI. |
| [`SecurityCheck.ps1`](../scripts/powershell/SecurityCheck.ps1) | PowerShell | Performs a basic security audit of the local Windows system. |
| [`SharePointManagement.ps1`](../scripts/powershell/SharePointManagement.ps1) | PowerShell | Basic management for SharePoint On-Premise and SharePoint Online. |
| [`TeamsManagement.ps1`](../scripts/powershell/TeamsManagement.ps1) | PowerShell | Manages Microsoft Teams. |
| [`Test-ScriptSyntax.ps1`](../scripts/powershell/Test-ScriptSyntax.ps1) | PowerShell |  |
| [`UserManagement.ps1`](../scripts/powershell/UserManagement.ps1) | PowerShell | Creates, removes, lists or imports local user accounts. |
| [`VMManagement.ps1`](../scripts/powershell/VMManagement.ps1) | PowerShell | Manages Hyper-V virtual machines. |

## pra

| Script | Langage | Description |
| --- | --- | --- |
| [`Invoke-PRA.ps1`](../pra/Invoke-PRA.ps1) | PowerShell |  |
| [`run-examples.ps1`](../pra/run-examples.ps1) | PowerShell | Test à blanc (sans actions destructives) |

## python

| Script | Langage | Description |
| --- | --- | --- |
| [`Install-CodexLocalLiteLLMAssets.ps1`](../scripts/python/Install-CodexLocalLiteLLMAssets.ps1) | PowerShell |  |
| [`Invoke-QwenLocal.ps1`](../scripts/python/Invoke-QwenLocal.ps1) | PowerShell |  |
| [`Manage-CodexCostRouting.ps1`](../scripts/python/Manage-CodexCostRouting.ps1) | PowerShell |  |
| [`Measure-QwenLocalSpeed.ps1`](../scripts/python/Measure-QwenLocalSpeed.ps1) | PowerShell |  |
| [`Start-CodexKeySessionWeb.ps1`](../scripts/python/Start-CodexKeySessionWeb.ps1) | PowerShell |  |
| [`Start-CodexQwenOllama.ps1`](../scripts/python/Start-CodexQwenOllama.ps1) | PowerShell |  |
| [`Switch-CodexLiteLLM.ps1`](../scripts/python/Switch-CodexLiteLLM.ps1) | PowerShell |  |
| [`Test-CodexLiteLLMDispatch.ps1`](../scripts/python/Test-CodexLiteLLMDispatch.ps1) | PowerShell |  |
| [`check_project_maturity.py`](../scripts/python/check_project_maturity.py) | Python | Validate the repository project-maturity catalog. |
| [`codex-cost-routing.cmd`](../scripts/python/codex-cost-routing.cmd) | Batch |  |
| [`codex_cost_profiles.py`](../scripts/python/codex_cost_profiles.py) | Python | Managed Codex profile fragments for the optional cost router. |
| [`codex_cost_router.py`](../scripts/python/codex_cost_router.py) | Python | Optional cost-routing wrapper for Codex CLI and a self-hosted LiteLLM OSS proxy. |
| [`codex_key_session_web.py`](../scripts/python/codex_key_session_web.py) | Python | Local-only web form for starting a LiteLLM Codex session with in-memory keys. |
| [`generate_index.py`](../scripts/python/generate_index.py) | Python | Generate docs/INDEX.md: a categorized catalog of every script in the repository. |
| [`healthcheck-litellm-routes.ps1`](../scripts/python/healthcheck-litellm-routes.ps1) | PowerShell |  |
| [`llm_bias_multi_agent.py`](../scripts/python/llm_bias_multi_agent.py) | Python | Generic multi-agent prompt-return manager for LLM outputs. |
| [`llm_decision_ledger.py`](../scripts/python/llm_decision_ledger.py) | Python | Provider-neutral decision ledger for LLM engineering workflows. |
| [`mcp_server.py`](../scripts/python/mcp_server.py) | Python | Read-only MCP server exposing the scripts stored in this repository. |
| [`measure-litellm-dispatch.ps1`](../scripts/python/measure-litellm-dispatch.ps1) | PowerShell |  |
| [`measure-risk-adjusted-dispatch.ps1`](../scripts/python/measure-risk-adjusted-dispatch.ps1) | PowerShell |  |
| [`measure-risk-adjusted-streaming.ps1`](../scripts/python/measure-risk-adjusted-streaming.ps1) | PowerShell |  |
| [`pentest_open_data.py`](../scripts/python/pentest_open_data.py) | Python | Enrich CVE identifiers with public defensive vulnerability data. |
| [`risk_adjusted_router.py`](../scripts/python/risk_adjusted_router.py) | Python |  |
| [`start-litellm-proxy.ps1`](../scripts/python/start-litellm-proxy.ps1) | PowerShell |  |
| [`start-risk-adjusted-router.ps1`](../scripts/python/start-risk-adjusted-router.ps1) | PowerShell |  |
| [`start_litellm_proxy.py`](../scripts/python/start_litellm_proxy.py) | Python |  |
| [`status-litellm-proxy.ps1`](../scripts/python/status-litellm-proxy.ps1) | PowerShell |  |
| [`stop-litellm-proxy.ps1`](../scripts/python/stop-litellm-proxy.ps1) | PowerShell |  |
| [`stop-risk-adjusted-router.ps1`](../scripts/python/stop-risk-adjusted-router.ps1) | PowerShell |  |

## python / openclaw_crewai_admin

| Script | Langage | Description |
| --- | --- | --- |
| [`container-entrypoint.sh`](../scripts/python/openclaw_crewai_admin/container-entrypoint.sh) | Bash |  |
| [`container-smoke-test.sh`](../scripts/python/openclaw_crewai_admin/container-smoke-test.sh) | Bash |  |
| [`crewai_admin_mcp.py`](../scripts/python/openclaw_crewai_admin/crewai_admin_mcp.py) | Python | Serveur MCP minimal pour administrer config/tasks.yaml de CrewAI. |
| [`install-vm.sh`](../scripts/python/openclaw_crewai_admin/deploy/install-vm.sh) | Bash |  |
| [`install-secure-container.sh`](../scripts/python/openclaw_crewai_admin/install-secure-container.sh) | Bash |  |
| [`setup.sh`](../scripts/python/openclaw_crewai_admin/setup.sh) | Bash |  |
| [`webhook_proxy.py`](../scripts/python/openclaw_crewai_admin/webhook_proxy.py) | Python | Proxy minimal : expose uniquement Google Chat, jamais le tableau de bord. |

## tokenized_llm_finance / contracts

| Script | Langage | Description |
| --- | --- | --- |
| [`AgentSettlementVault.sol`](../tokenized_llm_finance/contracts/AgentSettlementVault.sol) | Solidity |  |
| [`BankRegistry.sol`](../tokenized_llm_finance/contracts/BankRegistry.sol) | Solidity |  |
| [`EuroSettlementToken.sol`](../tokenized_llm_finance/contracts/EuroSettlementToken.sol) | Solidity |  |
| [`InterbankSettlement.sol`](../tokenized_llm_finance/contracts/InterbankSettlement.sol) | Solidity |  |
| [`PIDBudgetController.sol`](../tokenized_llm_finance/contracts/PIDBudgetController.sol) | Solidity |  |
| [`ReversibleRandomTimelock.sol`](../tokenized_llm_finance/contracts/ReversibleRandomTimelock.sol) | Solidity |  |
| [`SignedWadMath.sol`](../tokenized_llm_finance/contracts/libraries/SignedWadMath.sol) | Solidity |  |

## tokenized_llm_finance / python

| Script | Langage | Description |
| --- | --- | --- |
| [`__init__.py`](../tokenized_llm_finance/python/llm_energy_settlement/__init__.py) | Python | Meter LLM energy and settle it through a reversible on-chain workflow. |
| [`__main__.py`](../tokenized_llm_finance/python/llm_energy_settlement/__main__.py) | Python |  |
| [`chain.py`](../tokenized_llm_finance/python/llm_energy_settlement/chain.py) | Python | web3.py clients for PID updates and reversible, attested settlements. |
| [`cli.py`](../tokenized_llm_finance/python/llm_energy_settlement/cli.py) | Python | Minimal command-line entry point for a metered LLM call and optional queueing. |
| [`market_config.py`](../tokenized_llm_finance/python/llm_energy_settlement/market_config.py) | Python | Environment-backed construction of the bounded market-pricing service. |
| [`market_pid.py`](../tokenized_llm_finance/python/llm_energy_settlement/market_pid.py) | Python | Bounded market-pressure transformation for PID oracle observations. |
| [`metering.py`](../tokenized_llm_finance/python/llm_energy_settlement/metering.py) | Python | Deterministic LiteLLM token-to-energy-to-EUR metering. |
| [`pricing.py`](../tokenized_llm_finance/python/llm_energy_settlement/pricing.py) | Python | Market-backed electricity and FX pricing with bounded automatic adjustments. |
| [`workflow.py`](../tokenized_llm_finance/python/llm_energy_settlement/workflow.py) | Python | End-to-end metering and queueing command for the autonomous supervisor. |

## tokenized_llm_finance / script

| Script | Langage | Description |
| --- | --- | --- |
| [`Deploy.s.sol`](../tokenized_llm_finance/script/Deploy.s.sol) | Solidity |  |
| [`FinalizeHandoff.s.sol`](../tokenized_llm_finance/script/FinalizeHandoff.s.sol) | Solidity |  |

## tokenized_llm_finance / test

| Script | Langage | Description |
| --- | --- | --- |
| [`Infrastructure.t.sol`](../tokenized_llm_finance/test/Infrastructure.t.sol) | Solidity |  |
| [`InterbankSettlement.t.sol`](../tokenized_llm_finance/test/InterbankSettlement.t.sol) | Solidity |  |

## tools

| Script | Langage | Description |
| --- | --- | --- |
| [`analyze-ai.sh`](../tools/analyze-ai.sh) | Bash |  |
| [`analyze_ai.py`](../tools/analyze_ai.py) | Python |  |
| [`refactor.sh`](../tools/refactor.sh) | Bash |  |
