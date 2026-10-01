"""Codex cost router: config responsibilities."""

from __future__ import annotations
import os
from pathlib import Path
from codex_cost_profiles import render_profiles

SCRIPT_DIR = Path(__file__).resolve().parent

CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))

CODEX_CONFIG = CODEX_HOME / "config.toml"

COST_ROUTING_CONFIG = CODEX_HOME / "cost-routing.config.toml"

COST_ROUTING_HF_CONFIG = CODEX_HOME / "cost-routing-hf.config.toml"

LOG_DIR = CODEX_HOME / "logs"

LOG_FILE = LOG_DIR / "cost_router.jsonl"

STATE_FILE = LOG_DIR / "cost_router_state.json"

CONFIG_BACKUP = LOG_DIR / "config.toml.cost_router_backup"

BEGIN_MARKER = "# BEGIN CODEX COST ROUTER"

END_MARKER = "# END CODEX COST ROUTER"

LIGHT_MODEL = "codex-light"

DEFAULT_MODEL = "codex-default"

LONG_MODEL = "codex-long"

DEEP_MODEL = "codex-deep"

LEGACY_CHEAP_MODEL = "codex-cheap"

LEGACY_STRONG_MODEL = "codex-strong"

SMALL_LOCAL_MODEL = "codex-small-local"

PHI_LOCAL_MODEL = "codex-phi-local"

CLAUDE_COMPLEX_MODEL = "codex-claude-complex"

HF_FAST_MODEL = "codex-hf-fast"

HF_CHEAP_MODEL = "codex-hf-cheap"

HF_DIRECT_MODEL = "openai/gpt-oss-120b:fastest"

QWEN_LOCAL_MODEL = "codex-qwen-local"

NO_OPENAI_MODEL = "codex-no-openai"

DEFAULT_MAX_INPUT_TOKENS = 12_000

DEFAULT_MAX_OUTPUT_TOKENS = 2_000

SMALL_TASK_MAX_OUTPUT_TOKENS = 64

SMALL_TASK_TARGET_TOKENS_PER_SECOND = 5.0

PROVIDERS = (
    "auto",
    "openai",
    "gemini",
    "huggingface",
    "local-small",
    "phi",
    "qwen",
    "claude",
    "no-openai",
)

CODEX_PROVIDERS = ("auto", "standard", "litellm", "huggingface")

LOCAL_SMALL_MODELS = {SMALL_LOCAL_MODEL, PHI_LOCAL_MODEL}

OLLAMA_MODELS = {SMALL_LOCAL_MODEL, PHI_LOCAL_MODEL, QWEN_LOCAL_MODEL}

LITELLM_REQUIRED_PROVIDERS = {"claude", "gemini", "no-openai"}

LITELLM_REQUIRED_MODELS = {CLAUDE_COMPLEX_MODEL, NO_OPENAI_MODEL}

MODELS = (
    LIGHT_MODEL,
    DEFAULT_MODEL,
    LONG_MODEL,
    DEEP_MODEL,
    LEGACY_CHEAP_MODEL,
    LEGACY_STRONG_MODEL,
    HF_FAST_MODEL,
    HF_CHEAP_MODEL,
    SMALL_LOCAL_MODEL,
    PHI_LOCAL_MODEL,
    CLAUDE_COMPLEX_MODEL,
    QWEN_LOCAL_MODEL,
    NO_OPENAI_MODEL,
)

LITELLM_HOST = "localhost"

LITELLM_PORT = 4000

OLLAMA_HOST = "127.0.0.1"

OLLAMA_PORT = 11434

OLLAMA_CHAT_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/chat"

PHI_OLLAMA_MODEL = "phi4-mini"

QWEN_OLLAMA_MODEL = "qwen2.5-coder:3b"

WINDOWS_LITELLM_FALLBACK = Path(r"C:\tmp\litellm-oss\Scripts\litellm.exe")

POLICY_FILE = SCRIPT_DIR / "codex-routing-policy.yaml"

DEFAULT_ADAPTIVE_ROUTER = {
    "enabled": False,
    "shadow_mode": True,
    "min_confidence_delta": 0.15,
    "overload_penalty": 0.35,
    "cold_start_penalty": 0.5,
    "performance_weight": 0.35,
    "min_performance_observations": 2,
    "cost_guard_enabled": True,
    "max_cost_multiplier": 2.0,
    "critical_risk_threshold": 0.65,
    "decay": 0.65,
    "max_history": 200,
}

DEFAULT_POLICY = {
    "default_provider": "auto",
    "default_codex_provider": "auto",
    "open_models_only": False,
    "avoid_openai": False,
    "max_cost_usd": 0.0,
    "task_provider_rules": {
        "simple": "local-small",
        "medium": "auto",
        "complex": "claude",
    },
    "fallback_order": ["standard", "litellm", "huggingface"],
    "adaptive_router": DEFAULT_ADAPTIVE_ROUTER,
}

MARKOV_STATES = ("healthy", "warming", "overloaded", "failing", "cooldown")

MARKOV_TRANSITIONS = {
    "healthy": {
        "healthy": 0.82,
        "warming": 0.14,
        "overloaded": 0.03,
        "failing": 0.01,
        "cooldown": 0.0,
    },
    "warming": {
        "healthy": 0.22,
        "warming": 0.50,
        "overloaded": 0.20,
        "failing": 0.05,
        "cooldown": 0.03,
    },
    "overloaded": {
        "healthy": 0.05,
        "warming": 0.20,
        "overloaded": 0.45,
        "failing": 0.22,
        "cooldown": 0.08,
    },
    "failing": {
        "healthy": 0.02,
        "warming": 0.08,
        "overloaded": 0.20,
        "failing": 0.50,
        "cooldown": 0.20,
    },
    "cooldown": {
        "healthy": 0.18,
        "warming": 0.25,
        "overloaded": 0.12,
        "failing": 0.05,
        "cooldown": 0.40,
    },
}

MARKOV_PRIOR = {
    "healthy": 0.72,
    "warming": 0.18,
    "overloaded": 0.06,
    "failing": 0.02,
    "cooldown": 0.02,
}

ESTIMATED_RATES = {
    LIGHT_MODEL: {"input": 0.20, "output": 0.80},
    DEFAULT_MODEL: {"input": 2.00, "output": 8.00},
    LONG_MODEL: {"input": 0.80, "output": 3.00},
    DEEP_MODEL: {"input": 2.50, "output": 10.00},
    LEGACY_CHEAP_MODEL: {"input": 0.20, "output": 0.80},
    LEGACY_STRONG_MODEL: {"input": 2.00, "output": 8.00},
    HF_CHEAP_MODEL: {"input": 0.10, "output": 0.30},
    HF_FAST_MODEL: {"input": 0.25, "output": 0.75},
    QWEN_LOCAL_MODEL: {"input": 0.0, "output": 0.0},
    SMALL_LOCAL_MODEL: {"input": 0.0, "output": 0.0},
    PHI_LOCAL_MODEL: {"input": 0.0, "output": 0.0},
    NO_OPENAI_MODEL: {"input": 0.40, "output": 1.50},
    CLAUDE_COMPLEX_MODEL: {"input": 3.0, "output": 15.0},
}

HF_TERMS = (
    "hugging face",
    "huggingface",
    "hf_token",
    "open model",
    "open-weight",
    "open weights",
    "multi-provider",
    "multi provider",
    "provider benchmark",
    "benchmark providers",
)

QWEN_TERMS = (
    "qwen",
    "auto-heberge",
    "auto heberge",
    "auto-hebergee",
    "ollama",
    "local llm",
    "openai-compatible local",
)

CLAUDE_TERMS = (
    "claude",
    "anthropic",
    "sonnet",
)

LONG_CONTEXT_TERMS = (
    "gros contexte",
    "long contexte",
    "long context",
    "large context",
    "logs",
    "fichier volumineux",
    "large file",
    "synthese",
    "summarize",
    "compare documents",
)

PROFILES = render_profiles(DEFAULT_MODEL, HF_DIRECT_MODEL)

PROFILE_BLOCK = PROFILES.managed_block

COST_ROUTING_PROFILE = PROFILES.litellm_profile

COST_ROUTING_HF_PROFILE = PROFILES.huggingface_profile
