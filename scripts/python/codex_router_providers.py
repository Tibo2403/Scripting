"""Codex cost router: providers responsibilities."""

from __future__ import annotations
import os
from typing import Any

import codex_router_availability as router_availability
import codex_router_config as router_config
import codex_router_prompt as router_prompt
import codex_router_storage as router_storage


def select_local_small_model(reason: str) -> tuple[str, str]:
    """Choose the fastest local small-task model with a remote fallback."""
    if router_availability.phi_available():
        guard_reason = router_storage.phi_throughput_guard_reason(
            router_storage.read_history()
        )
        if guard_reason and router_availability.qwen_available():
            return (
                router_config.QWEN_LOCAL_MODEL,
                f"Phi latency guard switched to Qwen: {guard_reason}; {reason}",
            )
        return router_config.SMALL_LOCAL_MODEL, (
            f"local small-task provider requested; capped at {router_config.SMALL_TASK_MAX_OUTPUT_TOKENS} "
            f"output tokens to target >= {router_config.SMALL_TASK_TARGET_TOKENS_PER_SECOND:.1f} tok/s; {reason}"
        )
    if router_availability.qwen_available():
        return (
            router_config.QWEN_LOCAL_MODEL,
            f"local small-task provider requested; Phi unavailable so Qwen selected; {reason}",
        )
    return (
        router_config.LIGHT_MODEL,
        "local small-task provider requested but Ollama is not listening; using light remote tier",
    )


def select_claude_model(reason: str) -> tuple[str, str]:
    """Choose Claude through LiteLLM when ready, otherwise keep Codex deep available."""
    has_key = router_availability.claude_available()
    has_proxy = router_availability.proxy_available()
    if has_key and has_proxy:
        return (
            router_config.CLAUDE_COMPLEX_MODEL,
            f"claude provider requested through active LiteLLM proxy; {reason}",
        )
    if has_key:
        return (
            router_config.DEEP_MODEL,
            "claude requested but LiteLLM proxy is inactive; using default deep Codex tier",
        )
    return (
        router_config.DEEP_MODEL,
        "claude requested but ANTHROPIC_API_KEY is missing; using default deep Codex tier",
    )


def default_provider() -> str:
    """Read the provider preference from the environment with a safe fallback."""
    provider = os.environ.get("CODEX_ROUTER_PROVIDER", "auto").casefold()
    return provider if provider in router_config.PROVIDERS else "auto"


def openai_avoidance_enabled(policy: dict[str, Any] | None = None) -> bool:
    """Return whether OpenAI should be avoided to preserve or bypass quota."""
    value = os.environ.get("CODEX_ROUTER_OPENAI_MODE", "").casefold()
    if value in {"avoid", "off", "depleted", "quota", "no-openai", "no_openai"}:
        return True
    if value in {"", "auto", "normal", "on"}:
        return bool(policy and policy.get("avoid_openai"))
    return False


def default_codex_provider() -> str:
    """Read the Codex-facing provider preference with a safe fallback."""
    provider = os.environ.get("CODEX_ROUTER_CODEX_PROVIDER", "auto").casefold()
    return provider if provider in router_config.CODEX_PROVIDERS else "auto"


def normalize_provider(provider: Any, fallback: str = "auto") -> str:
    """Normalize a LiteLLM-side provider preference."""
    value = str(provider or fallback).casefold()
    return value if value in router_config.PROVIDERS else fallback


def normalize_codex_provider(provider: Any, fallback: str = "auto") -> str:
    """Normalize a Codex-facing provider preference."""
    value = str(provider or fallback).casefold()
    return value if value in router_config.CODEX_PROVIDERS else fallback


def resolve_auto_codex_provider() -> tuple[str, str]:
    """Choose the live Codex path: LiteLLM when active, otherwise normal Codex."""
    if router_availability.litellm_disabled():
        return "standard", "LiteLLM bypassed by CODEX_ROUTER_DISABLE_LITELLM"
    if router_availability.proxy_available():
        return "litellm", "LiteLLM proxy detected for Gemini/Qwen aliases"
    return "standard", "standard Codex path; LiteLLM proxy is inactive"


def resolve_codex_provider_choice(provider: Any, source: str) -> tuple[str, str]:
    """Resolve explicit or auto Codex provider choices into an executable path."""
    normalized = normalize_codex_provider(provider)
    if normalized == "litellm" and router_availability.litellm_disabled():
        return "standard", f"{source}: LiteLLM bypassed by CODEX_ROUTER_DISABLE_LITELLM"
    if normalized == "auto":
        resolved, reason = resolve_auto_codex_provider()
        return resolved, f"{source}: {reason}"
    return normalized, source


def provider_from_policy(
    prompt: str,
    requested_provider: str | None,
    policy: dict[str, Any],
) -> tuple[str, str]:
    """Resolve the LiteLLM-side provider from CLI, policy, and task class."""
    if requested_provider:
        return normalize_provider(requested_provider), "provider forced by CLI option"
    if os.environ.get("CODEX_ROUTER_PROVIDER"):
        return default_provider(), "provider forced by CODEX_ROUTER_PROVIDER"
    if bool(policy.get("open_models_only")):
        return "huggingface", "policy open_models_only"
    if openai_avoidance_enabled(policy):
        return "no-openai", "OpenAI avoidance enabled"
    complexity, _ = router_prompt.classify_complexity(prompt)
    rules = policy.get("task_provider_rules", {})
    if isinstance(rules, dict) and complexity in rules:
        return normalize_provider(rules[complexity]), f"policy task rule: {complexity}"
    return normalize_provider(policy.get("default_provider")), "policy default_provider"


def codex_provider_from_policy(
    requested_provider: str | None,
    policy: dict[str, Any],
) -> tuple[str, str]:
    """Resolve the Codex-facing provider from CLI and policy."""
    if requested_provider:
        return resolve_codex_provider_choice(
            requested_provider, "codex provider forced by CLI option"
        )
    if os.environ.get("CODEX_ROUTER_CODEX_PROVIDER"):
        return resolve_codex_provider_choice(
            default_codex_provider(),
            "codex provider forced by CODEX_ROUTER_CODEX_PROVIDER",
        )
    if bool(policy.get("open_models_only")):
        return "huggingface", "policy open_models_only"
    return resolve_codex_provider_choice(
        policy.get("default_codex_provider"),
        "policy default_codex_provider",
    )


def fallback_order_from_policy(
    selected_provider: str,
    policy: dict[str, Any],
) -> list[str]:
    """Return a de-duplicated Codex provider fallback order."""
    raw_order = policy.get("fallback_order", [])
    order = [normalize_codex_provider(item) for item in raw_order if item]
    result: list[str] = []
    for item in [selected_provider, *order, "standard"]:
        if item == "auto":
            continue
        if item not in result:
            result.append(item)
    return result or ["standard"]


def request_needs_litellm(provider: str, model: str) -> bool:
    """Return whether a routed request needs the LiteLLM proxy path."""
    return (
        provider in router_config.LITELLM_REQUIRED_PROVIDERS
        or model in router_config.LITELLM_REQUIRED_MODELS
    )


def prefer_provider(order: list[str], preferred: str) -> list[str]:
    """Move a provider to the front while preserving the rest of the order."""
    normalized = [normalize_codex_provider(item) for item in order if item]
    result: list[str] = []
    for item in [preferred, *normalized, "standard"]:
        if item == "auto":
            continue
        if item not in result:
            result.append(item)
    return result


def traffic_preserving_fallback_order(
    selected_codex_provider: str,
    effective_provider: str,
    model: str,
    policy: dict[str, Any],
    preserve_direct_traffic: bool = True,
) -> list[str]:
    """Keep normal Codex traffic direct while preserving explicit proxy routes."""
    order = fallback_order_from_policy(selected_codex_provider, policy)
    if selected_codex_provider == "huggingface":
        return order
    if request_needs_litellm(effective_provider, model):
        return prefer_provider(order, "litellm")
    if not preserve_direct_traffic:
        return order
    return prefer_provider(order, "standard")


def preserve_direct_traffic_order(
    order: list[str],
    selected_codex_provider: str,
    effective_provider: str,
    model: str,
    preserve_direct_traffic: bool = True,
) -> list[str]:
    """Prevent additive proxy routes from becoming the default traffic path."""
    if selected_codex_provider == "huggingface":
        return order
    if request_needs_litellm(effective_provider, model):
        return prefer_provider(order, "litellm")
    if not preserve_direct_traffic:
        return order
    return prefer_provider(order, "standard")


def should_preserve_direct_traffic(
    requested_provider: str | None, policy: dict[str, Any]
) -> bool:
    """Return whether proxy expansion should keep the direct Codex path first."""
    if requested_provider:
        return normalize_codex_provider(requested_provider) == "auto"
    if os.environ.get("CODEX_ROUTER_CODEX_PROVIDER"):
        return default_codex_provider() == "auto"
    if bool(policy.get("open_models_only")):
        return False
    return normalize_codex_provider(policy.get("default_codex_provider")) == "auto"


def codex_profile(provider: str) -> str:
    """Map a Codex-facing provider to the managed profile name."""
    if provider == "huggingface":
        return "cost-routing-hf"
    if provider == "litellm":
        return "cost-routing"
    return "standard"


def codex_model(model: str, provider: str) -> str:
    """Map router aliases to the model name expected by the selected profile."""
    if provider == "huggingface":
        return router_config.HF_DIRECT_MODEL
    if provider == "standard" and model in router_config.OLLAMA_MODELS:
        return model
    if provider == "standard":
        return "codex default"
    return model


def codex_provider_ready(provider: str) -> tuple[bool, str]:
    """Check local prerequisites for a Codex-facing provider."""
    if provider == "standard":
        return True, "standard Codex path is always available when Codex CLI exists."
    if provider == "huggingface":
        return (
            router_availability.hf_available(),
            "HF_TOKEN is required for the cost-routing-hf Codex profile.",
        )
    if router_availability.litellm_disabled():
        return False, "LiteLLM is disabled by CODEX_ROUTER_DISABLE_LITELLM."
    return (
        router_availability.proxy_available(),
        "LiteLLM OSS proxy is not listening on http://localhost:4000.",
    )


def build_codex_command(
    codex: str,
    provider: str,
    model: str,
    codex_args: list[str],
    prompt: str,
) -> list[str]:
    """Build a Codex exec command for either the normal path or a managed profile."""
    if provider == "standard":
        return [codex, "exec", *codex_args, prompt]
    return [
        codex,
        "exec",
        "--profile",
        codex_profile(provider),
        "--model",
        codex_model(model, provider),
        *codex_args,
        prompt,
    ]
