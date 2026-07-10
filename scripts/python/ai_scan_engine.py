"""Shared OpenAI-compatible engine configuration for defensive AI scans."""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass


AI_PROVIDER_DEFAULTS = {
    "openai-compatible": {
        "endpoint": "http://127.0.0.1:4000/v1",
        "model": "codex-default",
        "api_key_env": "LITELLM_API_KEY",
    },
    "glm": {
        "endpoint": "https://api.z.ai/api/paas/v4",
        "model": "glm-4.5-air",
        "api_key_env": "ZAI_API_KEY",
    },
}


@dataclass(frozen=True)
class AIEngineConfig:
    """Resolved, secret-free description of one analyzer or reviewer engine."""

    provider: str
    endpoint: str
    model: str
    api_key_env: str

    def as_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "endpoint": self.endpoint,
            "model": self.model,
            "api_key_env": self.api_key_env,
        }


def resolve_ai_engine_config(
    provider: str,
    endpoint: str | None = None,
    model: str | None = None,
    api_key_env: str | None = None,
) -> AIEngineConfig:
    """Resolve a preset while allowing every non-secret setting to be overridden."""
    if provider not in AI_PROVIDER_DEFAULTS:
        raise ValueError(f"Unsupported AI provider: {provider}")
    defaults = AI_PROVIDER_DEFAULTS[provider]
    return AIEngineConfig(
        provider=provider,
        endpoint=endpoint or os.getenv("AI_SECURITY_API_BASE") or defaults["endpoint"],
        model=model or os.getenv("AI_SECURITY_MODEL") or defaults["model"],
        api_key_env=api_key_env or defaults["api_key_env"],
    )


def resolve_ai_engine(
    provider: str,
    endpoint: str | None,
    model: str | None,
    api_key_env: str | None,
) -> dict[str, str]:
    """Backward-compatible dictionary view used by the scanner and callers."""
    return resolve_ai_engine_config(provider, endpoint, model, api_key_env).as_dict()


def call_ai(endpoint: str, api_key: str | None, model: str, prompt: str, timeout: float) -> str:
    """Call an OpenAI-compatible chat-completions endpoint."""
    base = endpoint.rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You write defensive security remediation plans."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()
