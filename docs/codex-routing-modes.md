# Codex Routing Modes

Use the simplest path that satisfies the current job.

| Mode | Use it when | Start command | Requires |
| --- | --- | --- | --- |
| Standard Codex | Daily coding, edits, reviews, and normal reliability. | `.\scripts\python\codex-cost-routing.cmd` | Codex CLI |
| LiteLLM profile | You want Gemini/API dispatch, local Qwen fallback through one gateway, or provider fallback rules. | `.\scripts\python\Manage-CodexCostRouting.ps1 -Action Start -CodexProvider LiteLLM` then `codex --profile cost-routing` | Local LiteLLM proxy and at least one provider key or local Qwen |
| Hugging Face profile | You explicitly want the direct Hugging Face router between Codex and an open model. | `.\scripts\python\Manage-CodexCostRouting.ps1 -CodexProvider HuggingFace` or `codex --profile cost-routing-hf` | `HF_TOKEN` |
| Direct Ollama Qwen | You want the fastest local small-task path and do not need Codex profiles or LiteLLM fallback. | `.\scripts\python\Invoke-QwenLocal.ps1 "prompt"` | Ollama with `qwen2.5-coder:3b` |
| Router dry-run | You want to see the chosen provider, model, and fallback order before running a task. | `python .\scripts\python\codex_cost_router.py run --dry-run "task"` | Python |
| Sovereign WebUI stack | You want a local Open WebUI + Ollama Docker stack for manual local-LLM use. | `bash scripts/bash/install_ia_souveraine.sh --gpu off --model mistral:7b` | Docker |

Default recommendation: keep Standard Codex for routine work. Start LiteLLM
only when you need provider dispatch or local gateway behavior, then stop it
after the session. Use direct Ollama for quick local checks where Codex
tooling is not needed.
