"""Select model aliases from prompt complexity and provider policy."""
from __future__ import annotations

import codex_router_availability as router_availability
import codex_router_config as router_config
import codex_router_prompt as router_prompt
import codex_router_providers as router_providers


def route_model(
    prompt: str,
    force_model: str | None = None,
    provider: str = "auto",
) -> tuple[str, str]:
    """Choose a LiteLLM model alias."""
    if force_model:
        return force_model, "model forced by CLI option"
    complexity, reason = router_prompt.classify_complexity(prompt)
    normalized = router_prompt.normalize_for_matching(prompt)
    wants_hf = any(term in normalized for term in router_config.HF_TERMS)
    wants_long_context = any(
        term in normalized for term in router_config.LONG_CONTEXT_TERMS
    )
    wants_claude = any(term in normalized for term in router_config.CLAUDE_TERMS)

    if provider == "huggingface":
        if router_availability.hf_available():
            model = (
                router_config.HF_CHEAP_MODEL
                if complexity == "simple"
                else router_config.HF_FAST_MODEL
            )
            return model, f"huggingface provider requested; {reason}"
        return (
            router_config.DEFAULT_MODEL,
            "huggingface requested but HF_TOKEN is missing; using default OpenAI/Gemini tier",
        )

    if provider in {"local-small", "phi"}:
        return router_providers.select_local_small_model(reason)

    if provider == "qwen":
        if router_availability.qwen_available():
            return router_config.QWEN_LOCAL_MODEL, f"qwen provider requested; {reason}"
        return (
            router_config.DEFAULT_MODEL,
            "qwen requested but Ollama is not listening on 127.0.0.1:11434; using default OpenAI/Gemini tier",
        )

    if provider == "claude":
        return router_providers.select_claude_model(reason)

    if provider == "no-openai":
        if router_availability.qwen_available():
            return (
                router_config.NO_OPENAI_MODEL,
                f"OpenAI avoided; Gemini/Qwen alias selected; {reason}",
            )
        return (
            router_config.LONG_MODEL,
            f"OpenAI avoided; Qwen unavailable so Gemini long-context alias selected; {reason}",
        )

    if provider == "openai":
        model = (
            router_config.LIGHT_MODEL
            if complexity == "simple"
            else router_config.DEEP_MODEL
        )
        return model, f"openai provider requested; {reason}"

    if provider == "gemini":
        model = (
            router_config.LIGHT_MODEL
            if complexity == "simple" and not wants_long_context
            else router_config.LONG_MODEL
        )
        return model, f"gemini provider requested; {reason}"

    if wants_hf and router_availability.hf_available():
        model = (
            router_config.HF_CHEAP_MODEL
            if complexity == "simple"
            else router_config.HF_FAST_MODEL
        )
        return model, f"huggingface-related task; {reason}"

    if (
        any(term in normalized for term in router_config.QWEN_TERMS)
        and router_availability.qwen_available()
    ):
        return router_config.QWEN_LOCAL_MODEL, f"qwen local task; {reason}"

    if (
        wants_claude
        and router_availability.claude_available()
        and router_availability.proxy_available()
    ):
        return (
            router_config.CLAUDE_COMPLEX_MODEL,
            f"claude-related task through active LiteLLM proxy; {reason}",
        )

    if wants_long_context:
        return router_config.LONG_MODEL, f"long-context task; {reason}"

    if complexity == "simple":
        model = router_config.LIGHT_MODEL
    elif complexity == "complex":
        model = router_config.DEEP_MODEL
    else:
        model = router_config.DEFAULT_MODEL
    return model, reason
