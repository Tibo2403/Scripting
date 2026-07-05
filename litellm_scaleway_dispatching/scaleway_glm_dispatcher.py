"""Scaleway GLM dispatching helpers for LiteLLM.

This module keeps the Scaleway / GLM provider configuration isolated from the
rest of a LiteLLM routing project. It is intentionally small so it can be used
from scripts, tests, or a future custom router.

Environment variables expected at runtime:
- SCALEWAY_API_KEY: API key used by Scaleway Generative APIs.
- SCALEWAY_BASE_URL: OpenAI-compatible base URL exposed by Scaleway.

The actual model id can be configured with SCALEWAY_GLM_MODEL or passed through
ScalewayGLMConfig(model=...).
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable, Iterable, Mapping, Sequence

try:  # LiteLLM is optional during unit tests because calls are injected.
    import litellm
except Exception:  # pragma: no cover - handled by dependency injection/tests
    litellm = None  # type: ignore[assignment]


DEFAULT_MODEL = "openai/glm-4.5"
DEFAULT_TIMEOUT_SECONDS = 60


class ScalewayGLMConfigurationError(ValueError):
    """Raised when required Scaleway GLM configuration is missing."""


@dataclass(frozen=True)
class ScalewayGLMConfig:
    """Configuration for a Scaleway OpenAI-compatible GLM deployment."""

    model: str = DEFAULT_MODEL
    api_key: str | None = None
    api_base: str | None = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "ScalewayGLMConfig":
        """Build configuration from environment variables."""

        return cls(
            model=os.getenv("SCALEWAY_GLM_MODEL", DEFAULT_MODEL),
            api_key=os.getenv("SCALEWAY_API_KEY"),
            api_base=os.getenv("SCALEWAY_BASE_URL"),
            timeout_seconds=int(os.getenv("SCALEWAY_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
        )

    def validate(self) -> None:
        """Validate mandatory runtime values."""

        missing = []
        if not self.api_key:
            missing.append("SCALEWAY_API_KEY")
        if not self.api_base:
            missing.append("SCALEWAY_BASE_URL")
        if missing:
            raise ScalewayGLMConfigurationError(
                "Missing required Scaleway GLM configuration: " + ", ".join(missing)
            )

    def completion_kwargs(self) -> dict[str, Any]:
        """Return LiteLLM-compatible provider kwargs."""

        self.validate()
        return {
            "model": self.model,
            "api_key": self.api_key,
            "api_base": self.api_base,
            "timeout": self.timeout_seconds,
        }


def normalize_messages(prompt_or_messages: str | Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    """Convert a prompt string or chat messages into OpenAI-style messages."""

    if isinstance(prompt_or_messages, str):
        return [{"role": "user", "content": prompt_or_messages}]

    messages: list[dict[str, str]] = []
    for message in prompt_or_messages:
        role = message.get("role")
        content = message.get("content")
        if not role or content is None:
            raise ValueError("Each message must contain 'role' and 'content'.")
        messages.append({"role": str(role), "content": str(content)})
    return messages


def scaleway_glm_completion(
    prompt_or_messages: str | Sequence[Mapping[str, str]],
    *,
    config: ScalewayGLMConfig | None = None,
    completion_func: Callable[..., Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Call Scaleway GLM through LiteLLM's OpenAI-compatible completion API.

    completion_func is injectable so tests can verify payloads without making a
    real network request or consuming provider tokens.
    """

    resolved_config = config or ScalewayGLMConfig.from_env()
    messages = normalize_messages(prompt_or_messages)
    provider_kwargs = resolved_config.completion_kwargs()

    if completion_func is None:
        if litellm is None:
            raise RuntimeError("litellm is not installed. Run `pip install litellm`.")
        completion_func = litellm.completion

    return completion_func(messages=messages, **provider_kwargs, **kwargs)


def dispatch_with_fallback(
    prompt_or_messages: str | Sequence[Mapping[str, str]],
    *,
    primary_config: ScalewayGLMConfig | None = None,
    fallback_models: Iterable[str] = (),
    completion_func: Callable[..., Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Try Scaleway GLM first, then fallback model ids if the primary fails.

    Fallbacks reuse the same LiteLLM completion function, which means they can be
    normal LiteLLM model ids such as `openai/gpt-4o-mini`, `azure/...`, or any
    provider configured in the caller's environment.
    """

    messages = normalize_messages(prompt_or_messages)
    resolved_config = primary_config or ScalewayGLMConfig.from_env()

    if completion_func is None:
        if litellm is None:
            raise RuntimeError("litellm is not installed. Run `pip install litellm`.")
        completion_func = litellm.completion

    errors: list[Exception] = []

    try:
        return completion_func(messages=messages, **resolved_config.completion_kwargs(), **kwargs)
    except Exception as exc:  # noqa: BLE001 - collecting provider failures for fallback
        errors.append(exc)

    for model in fallback_models:
        try:
            return completion_func(messages=messages, model=model, **kwargs)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    raise RuntimeError(f"All LiteLLM dispatch attempts failed: {errors}")
