"""Codex cost router: availability responsibilities."""

from __future__ import annotations
import os
import re
import shutil
import socket
from pathlib import Path

import codex_router_config as router_config
import codex_router_storage as router_storage


def hf_available() -> bool:
    """Return whether Hugging Face routing can be used in this shell."""
    return bool(os.environ.get("HF_TOKEN"))


def ollama_available() -> bool:
    """Return whether the local Ollama OpenAI-compatible endpoint is reachable."""
    try:
        with socket.create_connection(
            (router_config.OLLAMA_HOST, router_config.OLLAMA_PORT), timeout=1
        ):
            return True
    except OSError:
        return False


def phi_available() -> bool:
    """Return whether local small-task routing can use Ollama Phi-4 Mini."""
    return ollama_available()


def qwen_available() -> bool:
    """Return whether the local Ollama Qwen endpoint is reachable."""
    return ollama_available()


def claude_available() -> bool:
    """Return whether Anthropic Claude routing can be used through LiteLLM."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def litellm_disabled() -> bool:
    """Return whether the local LiteLLM path is explicitly bypassed."""
    return os.environ.get("CODEX_ROUTER_DISABLE_LITELLM", "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def find_codex() -> str | None:
    """Locate Codex CLI without assuming a specific Windows installation path."""
    configured = os.environ.get("CODEX_CLI_PATH")
    if configured and Path(configured).is_file():
        return configured

    match = re.search(
        r"""(?m)^\s*CODEX_CLI_PATH\s*=\s*['"]([^'"]+)['"]""",
        router_storage.read_text(router_config.CODEX_CONFIG),
    )
    if match:
        configured = match.group(1)
        if Path(configured).is_file():
            return configured

    return shutil.which("codex")


def find_litellm() -> str | None:
    """Locate LiteLLM CLI, including the documented short-path Windows venv."""
    configured = os.environ.get("LITELLM_CLI_PATH")
    if configured and Path(configured).is_file():
        return configured
    discovered = shutil.which("litellm")
    if discovered:
        return discovered
    if router_config.WINDOWS_LITELLM_FALLBACK.is_file():
        return str(router_config.WINDOWS_LITELLM_FALLBACK)
    return None


def proxy_available() -> bool:
    """Check whether the local LiteLLM OSS proxy is accepting TCP connections."""
    if litellm_disabled():
        return False
    try:
        with socket.create_connection(
            (router_config.LITELLM_HOST, router_config.LITELLM_PORT), timeout=1
        ):
            return True
    except OSError:
        return False
