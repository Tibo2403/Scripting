"""Production-oriented Scaleway GLM dispatching helpers for LiteLLM.

The module is intentionally provider-light: Scaleway is called through
LiteLLM's OpenAI-compatible path, while endpoint, model and secrets stay
configured outside source control.

Environment variables:
- SCALEWAY_API_KEY: secret API key.
- SCALEWAY_BASE_URL: OpenAI-compatible base URL, including /v1 when required.
- SCALEWAY_GLM_MODEL: LiteLLM model id, for example openai/<scaleway-model-id>.
- SCALEWAY_TIMEOUT_SECONDS: optional positive integer timeout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
import time
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlparse

try:  # LiteLLM is optional during unit tests because calls are injected.
    import litellm
except ImportError:  # pragma: no cover - handled by dependency injection/tests
    litellm = None  # type: ignore[assignment]


DEFAULT_MODEL = "openai/glm-4.5"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_RETRIES = 2
DEFAULT_BACKOFF_SECONDS = 0.25


class ScalewayGLMConfigurationError(ValueError):
    """Raised when required Scaleway GLM configuration is missing or invalid."""


class DispatchError(RuntimeError):
    """Raised when all dispatch attempts fail."""


class ErrorKind(str, Enum):
    """Normalized provider error class used by retry/fallback decisions."""

    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    SERVER = "server"
    BAD_REQUEST = "bad_request"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RetryPolicy:
    """Retry policy for transient provider errors."""

    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS
    retryable_errors: frozenset[ErrorKind] = field(
        default_factory=lambda: frozenset(
            {ErrorKind.RATE_LIMIT, ErrorKind.TIMEOUT, ErrorKind.SERVER, ErrorKind.UNKNOWN}
        )
    )

    def validate(self) -> None:
        if self.max_retries < 0:
            raise ScalewayGLMConfigurationError("max_retries must be >= 0.")
        if self.backoff_seconds < 0:
            raise ScalewayGLMConfigurationError("backoff_seconds must be >= 0.")


@dataclass(frozen=True)
class DispatchAttempt:
    """Metrics for one provider attempt."""

    model: str
    provider: str
    attempt_number: int
    success: bool
    latency_ms: float
    error_kind: ErrorKind | None = None
    error_message: str | None = None


@dataclass
class DispatchResult:
    """Response plus dispatch metrics."""

    response: Any
    selected_model: str
    attempts: list[DispatchAttempt]


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

        timeout_raw = os.getenv("SCALEWAY_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        try:
            timeout_seconds = int(timeout_raw)
        except ValueError as exc:
            raise ScalewayGLMConfigurationError(
                "SCALEWAY_TIMEOUT_SECONDS must be a positive integer."
            ) from exc

        return cls(
            model=os.getenv("SCALEWAY_GLM_MODEL", DEFAULT_MODEL),
            api_key=os.getenv("SCALEWAY_API_KEY"),
            api_base=os.getenv("SCALEWAY_BASE_URL"),
            timeout_seconds=timeout_seconds,
        )

    def validate(self) -> None:
        """Validate mandatory runtime values before calling LiteLLM."""

        missing = []
        if not self.api_key:
            missing.append("SCALEWAY_API_KEY")
        if not self.api_base:
            missing.append("SCALEWAY_BASE_URL")
        if not self.model:
            missing.append("SCALEWAY_GLM_MODEL")
        if missing:
            raise ScalewayGLMConfigurationError(
                "Missing required Scaleway GLM configuration: " + ", ".join(missing)
            )

        parsed = urlparse(str(self.api_base))
        if parsed.scheme != "https" or not parsed.netloc:
            raise ScalewayGLMConfigurationError(
                "SCALEWAY_BASE_URL must be a valid https URL, for example "
                "https://<scaleway-openai-compatible-endpoint>/v1."
            )

        if "/v1" not in parsed.path.rstrip("/"):
            raise ScalewayGLMConfigurationError(
                "SCALEWAY_BASE_URL should include the OpenAI-compatible /v1 path."
            )

        if "/" not in self.model:
            raise ScalewayGLMConfigurationError(
                "SCALEWAY_GLM_MODEL should include a LiteLLM provider prefix, "
                "for example openai/<scaleway-model-id>."
            )

        if self.timeout_seconds <= 0:
            raise ScalewayGLMConfigurationError("timeout_seconds must be > 0.")

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
        stripped = prompt_or_messages.strip()
        if not stripped:
            raise ValueError("Prompt cannot be empty.")
        return [{"role": "user", "content": stripped}]

    messages: list[dict[str, str]] = []
    for message in prompt_or_messages:
        role = message.get("role")
        content = message.get("content")
        if not role or content is None:
            raise ValueError("Each message must contain 'role' and 'content'.")
        messages.append({"role": str(role), "content": str(content)})
    if not messages:
        raise ValueError("Messages cannot be empty.")
    return messages


def classify_error(exc: Exception) -> ErrorKind:
    """Best-effort classification for provider exceptions."""

    text = f"{type(exc).__name__}: {exc}".lower()

    if any(token in text for token in ("401", "403", "unauthorized", "forbidden", "auth")):
        return ErrorKind.AUTH
    if any(token in text for token in ("429", "rate limit", "too many requests", "quota")):
        return ErrorKind.RATE_LIMIT
    if any(token in text for token in ("timeout", "timed out", "deadline")):
        return ErrorKind.TIMEOUT
    if any(token in text for token in ("500", "502", "503", "504", "server", "unavailable")):
        return ErrorKind.SERVER
    if any(token in text for token in ("400", "bad request", "invalid model", "unsupported")):
        return ErrorKind.BAD_REQUEST
    return ErrorKind.UNKNOWN


def _resolve_completion_func(completion_func: Callable[..., Any] | None) -> Callable[..., Any]:
    if completion_func is not None:
        return completion_func
    if litellm is None:
        raise RuntimeError("litellm is not installed. Run `pip install litellm`.")
    return litellm.completion


def _call_with_retries(
    *,
    model: str,
    provider: str,
    messages: list[dict[str, str]],
    completion_func: Callable[..., Any],
    retry_policy: RetryPolicy,
    sleep_func: Callable[[float], None],
    attempts: list[DispatchAttempt],
    provider_kwargs: Mapping[str, Any],
    request_kwargs: Mapping[str, Any],
) -> Any:
    retry_policy.validate()
    last_error: Exception | None = None

    for attempt_number in range(1, retry_policy.max_retries + 2):
        started = time.perf_counter()
        try:
            response = completion_func(
                messages=messages,
                **dict(provider_kwargs),
                **dict(request_kwargs),
            )
            latency_ms = (time.perf_counter() - started) * 1000
            attempts.append(
                DispatchAttempt(
                    model=model,
                    provider=provider,
                    attempt_number=attempt_number,
                    success=True,
                    latency_ms=latency_ms,
                )
            )
            return response
        except Exception as exc:  # noqa: BLE001 - provider exceptions vary by backend
            latency_ms = (time.perf_counter() - started) * 1000
            error_kind = classify_error(exc)
            attempts.append(
                DispatchAttempt(
                    model=model,
                    provider=provider,
                    attempt_number=attempt_number,
                    success=False,
                    latency_ms=latency_ms,
                    error_kind=error_kind,
                    error_message=str(exc),
                )
            )
            last_error = exc

            is_last_attempt = attempt_number >= retry_policy.max_retries + 1
            if is_last_attempt or error_kind not in retry_policy.retryable_errors:
                break

            sleep_func(retry_policy.backoff_seconds * attempt_number)

    assert last_error is not None
    raise last_error


def scaleway_glm_completion(
    prompt_or_messages: str | Sequence[Mapping[str, str]],
    *,
    config: ScalewayGLMConfig | None = None,
    completion_func: Callable[..., Any] | None = None,
    retry_policy: RetryPolicy | None = None,
    return_metrics: bool = False,
    sleep_func: Callable[[float], None] = time.sleep,
    **kwargs: Any,
) -> Any | DispatchResult:
    """Call Scaleway GLM through LiteLLM's OpenAI-compatible completion API."""

    resolved_config = config or ScalewayGLMConfig.from_env()
    messages = normalize_messages(prompt_or_messages)
    completion = _resolve_completion_func(completion_func)
    policy = retry_policy or RetryPolicy()
    attempts: list[DispatchAttempt] = []

    response = _call_with_retries(
        model=resolved_config.model,
        provider="scaleway",
        messages=messages,
        completion_func=completion,
        retry_policy=policy,
        sleep_func=sleep_func,
        attempts=attempts,
        provider_kwargs=resolved_config.completion_kwargs(),
        request_kwargs=kwargs,
    )

    if return_metrics:
        return DispatchResult(response=response, selected_model=resolved_config.model, attempts=attempts)
    return response


def dispatch_with_fallback(
    prompt_or_messages: str | Sequence[Mapping[str, str]],
    *,
    primary_config: ScalewayGLMConfig | None = None,
    fallback_models: Iterable[str] = (),
    completion_func: Callable[..., Any] | None = None,
    retry_policy: RetryPolicy | None = None,
    return_metrics: bool = False,
    sleep_func: Callable[[float], None] = time.sleep,
    **kwargs: Any,
) -> Any | DispatchResult:
    """Try Scaleway GLM first, then fallback model ids if the primary fails."""

    messages = normalize_messages(prompt_or_messages)
    resolved_config = primary_config or ScalewayGLMConfig.from_env()
    completion = _resolve_completion_func(completion_func)
    policy = retry_policy or RetryPolicy()
    attempts: list[DispatchAttempt] = []

    try:
        response = _call_with_retries(
            model=resolved_config.model,
            provider="scaleway",
            messages=messages,
            completion_func=completion,
            retry_policy=policy,
            sleep_func=sleep_func,
            attempts=attempts,
            provider_kwargs=resolved_config.completion_kwargs(),
            request_kwargs=kwargs,
        )
        if return_metrics:
            return DispatchResult(response=response, selected_model=resolved_config.model, attempts=attempts)
        return response
    except Exception:
        pass

    for fallback_model in fallback_models:
        fallback_model = str(fallback_model).strip()
        if not fallback_model:
            continue
        try:
            response = _call_with_retries(
                model=fallback_model,
                provider="fallback",
                messages=messages,
                completion_func=completion,
                retry_policy=policy,
                sleep_func=sleep_func,
                attempts=attempts,
                provider_kwargs={"model": fallback_model},
                request_kwargs=kwargs,
            )
            if return_metrics:
                return DispatchResult(response=response, selected_model=fallback_model, attempts=attempts)
            return response
        except Exception:
            continue

    raise DispatchError(f"All LiteLLM dispatch attempts failed after {len(attempts)} attempts.")
