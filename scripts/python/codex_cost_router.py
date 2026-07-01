"""Optional cost-routing wrapper for Codex CLI and a self-hosted LiteLLM OSS proxy."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
CODEX_CONFIG = CODEX_HOME / "config.toml"
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
PROVIDERS = ("auto", "openai", "gemini", "huggingface", "local-small", "phi", "qwen", "claude", "no-openai")
CODEX_PROVIDERS = ("auto", "standard", "litellm", "huggingface")
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
OLLAMA_CHAT_COMPLETIONS_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/v1/chat/completions"
PHI_OLLAMA_MODEL = "phi4-mini"
QWEN_OLLAMA_MODEL = "qwen2.5-coder:3b"
WINDOWS_LITELLM_FALLBACK = Path(r"C:\tmp\litellm-oss\Scripts\litellm.exe")
POLICY_FILE = Path(__file__).with_name("codex-routing-policy.yaml")
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
    "fallback_order": ["litellm", "standard", "huggingface"],
    "adaptive_router": DEFAULT_ADAPTIVE_ROUTER,
}
MARKOV_STATES = ("healthy", "warming", "overloaded", "failing", "cooldown")
MARKOV_TRANSITIONS = {
    "healthy": {"healthy": 0.82, "warming": 0.14, "overloaded": 0.03, "failing": 0.01, "cooldown": 0.0},
    "warming": {"healthy": 0.22, "warming": 0.50, "overloaded": 0.20, "failing": 0.05, "cooldown": 0.03},
    "overloaded": {"healthy": 0.05, "warming": 0.20, "overloaded": 0.45, "failing": 0.22, "cooldown": 0.08},
    "failing": {"healthy": 0.02, "warming": 0.08, "overloaded": 0.20, "failing": 0.50, "cooldown": 0.20},
    "cooldown": {"healthy": 0.18, "warming": 0.25, "overloaded": 0.12, "failing": 0.05, "cooldown": 0.40},
}
MARKOV_PRIOR = {"healthy": 0.72, "warming": 0.18, "overloaded": 0.06, "failing": 0.02, "cooldown": 0.02}

# Approximate placeholders in USD per million tokens. Adjust these estimates to
# match the deployments configured in your local LiteLLM OSS proxy.
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

SIMPLE_TERMS = (
    "correction mineure",
    "resume",
    "documentation",
    "document",
    "petite modification",
    "typo",
    "readme",
)
MEDIUM_TERMS = (
    "refactor",
    "test",
    "docker",
    "api",
    "python",
    "typescript",
)
COMPLEX_TERMS = (
    "securite",
    "security",
    "fiscalite",
    "odoo",
    "architecture",
    "migration",
    "production",
    "rls",
    "supabase",
    "bug critique",
    "critical bug",
)
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
PROFILE_BLOCK = f"""\
# BEGIN CODEX COST ROUTER
[model_providers.litellm]
name = "LiteLLM OSS Cost Router"
base_url = "http://localhost:4000/v1"
env_key = "LITELLM_API_KEY"

[model_providers.huggingface]
name = "Hugging Face Inference Providers"
base_url = "https://router.huggingface.co/v1"
env_key = "HF_TOKEN"
wire_api = "chat"

[profiles.cost-routing]
model = "{DEFAULT_MODEL}"
model_provider = "litellm"
model_reasoning_effort = "medium"
model_verbosity = "low"
model_auto_compact_token_limit = 64000
tool_output_token_limit = 8000

[profiles.cost-routing-hf]
model = "{HF_DIRECT_MODEL}"
model_provider = "huggingface"
model_reasoning_effort = "low"
# END CODEX COST ROUTER
"""


def utc_now() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def ensure_directories() -> None:
    """Create Codex directories used by this optional tool."""
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    """Read UTF-8 text when a file exists."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, content: str) -> None:
    """Write UTF-8 text after creating the parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def remove_profile_block(config: str) -> str:
    """Remove only the managed profile block from a Codex config file."""
    pattern = re.compile(
        rf"\n?{re.escape(BEGIN_MARKER)}.*?{re.escape(END_MARKER)}\n?",
        flags=re.DOTALL,
    )
    return pattern.sub("\n", config).rstrip() + ("\n" if config.strip() else "")


def load_state() -> dict[str, Any]:
    """Load local router state without failing on a damaged state file."""
    try:
        return json.loads(read_text(STATE_FILE)) if STATE_FILE.exists() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(**updates: Any) -> dict[str, Any]:
    """Merge and store local router state."""
    state = load_state()
    state.update(updates)
    write_text(STATE_FILE, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    return state


def append_log(record: dict[str, Any]) -> None:
    """Append a JSONL routing record without storing prompts or API keys."""
    ensure_directories()
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_history() -> list[dict[str, Any]]:
    """Read valid JSONL routing records."""
    records: list[dict[str, Any]] = []
    if not LOG_FILE.exists():
        return records
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def clean_text(text: str) -> str:
    """Remove HTML, long comments, duplicate lines, and unnecessary whitespace."""
    text = re.sub(r"(?is)<script.*?>.*?</script>|<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)/\*.{500,}?\*/", "/* long comment removed */", text)
    text = re.sub(r"(?m)^\s*(#|//).{500,}$", r"\1 long comment removed", text)
    text = re.sub(r"<[^>]+>", " ", text)

    result: list[str] = []
    previous = ""
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            if result and result[-1] != "":
                result.append("")
            continue
        if line == previous:
            continue
        result.append(line)
        previous = line
    return "\n".join(result).strip()


def compress_logs(text: str) -> str:
    """Collapse repetitive logs and remove noisy low-value lines."""
    lines = text.splitlines()
    result: list[str] = []
    counts: dict[str, int] = {}
    noise = re.compile(
        r"(?i)\b(debug|trace|verbose|progress|downloaded|transformed|rendering chunks)\b"
    )
    for line in lines:
        normalized = re.sub(r"\d+", "<n>", line.strip())
        if noise.search(line) and not re.search(r"(?i)\b(error|fail|warning|exception)\b", line):
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
        if counts[normalized] <= 2:
            result.append(line)
        elif counts[normalized] == 3:
            result.append(f"[repeated log lines omitted: {normalized}]")
    return "\n".join(result)


def estimate_tokens(text: str) -> int:
    """Estimate tokens conservatively without requiring a tokenizer package."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def normalize_for_matching(text: str) -> str:
    """Lowercase text and strip accents for stable keyword matching."""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def smart_truncate(text: str, max_tokens: int) -> str:
    """Keep the beginning and end of oversized context with a clear marker."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    marker = "\n\n[... context truncated by codex_cost_router ...]\n\n"
    remaining = max(0, max_chars - len(marker))
    head = int(remaining * 0.70)
    tail = remaining - head
    return text[:head].rstrip() + marker + text[-tail:].lstrip()


def classify_complexity(prompt: str) -> tuple[str, str]:
    """Classify a task using explicit, explainable keyword rules."""
    normalized = normalize_for_matching(prompt)
    complex_matches = [term for term in COMPLEX_TERMS if term in normalized]
    medium_matches = [term for term in MEDIUM_TERMS if term in normalized]
    simple_matches = [term for term in SIMPLE_TERMS if term in normalized]

    if complex_matches:
        return "complex", f"complex keyword: {', '.join(complex_matches[:3])}"
    if medium_matches or estimate_tokens(prompt) > 1_500:
        detail = ", ".join(medium_matches[:3]) or "large prompt"
        return "medium", f"medium complexity: {detail}"
    if simple_matches:
        return "simple", f"simple task: {', '.join(simple_matches[:3])}"
    return "medium", "default routing for an unclassified task"


def _parse_scalar(value: str) -> Any:
    """Parse a tiny YAML scalar subset without requiring PyYAML."""
    value = value.strip().strip("'\"")
    lowered = value.casefold()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def parse_simple_policy(text: str) -> dict[str, Any]:
    """Parse the small policy YAML shape used by this router."""
    policy: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        line = raw_line.split("#", 1)[0].rstrip()
        if line.startswith("  - ") and current_key:
            policy.setdefault(current_key, []).append(_parse_scalar(line[4:]))
            continue
        if line.startswith("  ") and current_key:
            key, _, value = line.strip().partition(":")
            if key and value:
                policy.setdefault(current_key, {})[key.strip()] = _parse_scalar(value)
            continue
        key, _, value = line.partition(":")
        current_key = key.strip()
        policy[current_key] = _parse_scalar(value) if value.strip() else ([] if current_key.endswith("_order") else {})
    return policy


def load_policy(path: Path = POLICY_FILE) -> dict[str, Any]:
    """Load routing policy with defaults and no hard PyYAML dependency."""
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    if not path.exists():
        return policy
    text = read_text(path)
    try:
        import yaml  # type: ignore[import-untyped]

        loaded = yaml.safe_load(text) or {}
    except Exception:
        loaded = parse_simple_policy(text)
    if not isinstance(loaded, dict):
        return policy
    for key, value in loaded.items():
        if key in {"task_provider_rules", "adaptive_router"} and isinstance(value, dict):
            policy[key].update(value)
        elif key in policy:
            policy[key] = value
    return policy


def hf_available() -> bool:
    """Return whether Hugging Face routing can be used in this shell."""
    return bool(os.environ.get("HF_TOKEN"))


def ollama_available() -> bool:
    """Return whether the local Ollama OpenAI-compatible endpoint is reachable."""
    try:
        with socket.create_connection((OLLAMA_HOST, OLLAMA_PORT), timeout=1):
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


def default_provider() -> str:
    """Read the provider preference from the environment with a safe fallback."""
    provider = os.environ.get("CODEX_ROUTER_PROVIDER", "auto").casefold()
    return provider if provider in PROVIDERS else "auto"


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
    return provider if provider in CODEX_PROVIDERS else "auto"


def normalize_provider(provider: Any, fallback: str = "auto") -> str:
    """Normalize a LiteLLM-side provider preference."""
    value = str(provider or fallback).casefold()
    return value if value in PROVIDERS else fallback


def normalize_codex_provider(provider: Any, fallback: str = "auto") -> str:
    """Normalize a Codex-facing provider preference."""
    value = str(provider or fallback).casefold()
    return value if value in CODEX_PROVIDERS else fallback


def resolve_auto_codex_provider() -> tuple[str, str]:
    """Choose the live Codex path: LiteLLM when active, otherwise normal Codex."""
    if proxy_available():
        return "litellm", "LiteLLM proxy detected for Gemini/Qwen aliases"
    return "standard", "standard Codex path; LiteLLM proxy is inactive"


def resolve_codex_provider_choice(provider: Any, source: str) -> tuple[str, str]:
    """Resolve explicit or auto Codex provider choices into an executable path."""
    normalized = normalize_codex_provider(provider)
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
    complexity, _ = classify_complexity(prompt)
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
        return resolve_codex_provider_choice(requested_provider, "codex provider forced by CLI option")
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


def truthy(value: Any) -> bool:
    """Parse policy booleans from Python or YAML-like scalar values."""
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def adaptive_router_config(policy: dict[str, Any]) -> dict[str, Any]:
    """Return adaptive router settings merged with conservative defaults."""
    config = dict(DEFAULT_ADAPTIVE_ROUTER)
    loaded = policy.get("adaptive_router", {})
    if isinstance(loaded, dict):
        config.update(loaded)
    config["enabled"] = truthy(config.get("enabled"))
    config["shadow_mode"] = truthy(config.get("shadow_mode"))
    config["min_confidence_delta"] = float(config.get("min_confidence_delta") or 0)
    config["overload_penalty"] = float(config.get("overload_penalty") or 0)
    config["cold_start_penalty"] = float(config.get("cold_start_penalty") or 0)
    config["performance_weight"] = clamp01(float(config.get("performance_weight") or 0))
    config["min_performance_observations"] = max(
        1,
        int(config.get("min_performance_observations") or 2),
    )
    config["cost_guard_enabled"] = truthy(config.get("cost_guard_enabled"))
    config["max_cost_multiplier"] = max(1.0, float(config.get("max_cost_multiplier") or 2.0))
    config["critical_risk_threshold"] = clamp01(float(config.get("critical_risk_threshold") or 0.65))
    config["decay"] = min(0.95, max(0.05, float(config.get("decay") or 0.65)))
    config["max_history"] = max(1, int(config.get("max_history") or 200))
    return config


def clamp01(value: float) -> float:
    """Clamp a score to the [0, 1] range."""
    return min(1.0, max(0.0, value))


def metric_pressure(value: Any, healthy: float, overloaded: float) -> float:
    """Convert a raw metric into a normalized overload pressure."""
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return 0.0
    if raw <= healthy:
        return 0.0
    if raw >= overloaded:
        return 1.0
    return (raw - healthy) / max(overloaded - healthy, 0.001)


def provider_observation_pressure(record: dict[str, Any]) -> float:
    """Estimate provider pressure from TTFT, latency, token pressure, cost, quality, and errors."""
    ttft = metric_pressure(record.get("ttft_ms"), 1_500, 6_000)
    latency = metric_pressure(record.get("latency_ms"), 8_000, 45_000)
    token_pressure = clamp01(float(record.get("token_pressure") or 0))
    cost = metric_pressure(record.get("estimated_cost_usd"), 0.01, 0.20)
    error_rate = clamp01(float(record.get("error_rate") or 0))
    success = record.get("success")
    failed = success is False or int(record.get("returncode") or 0) != 0 or bool(record.get("error"))
    quality = record.get("quality_score")
    quality_pressure = 0.0
    if quality is not None:
        quality_pressure = 1.0 - clamp01(float(quality))
    pressure = (
        0.22 * ttft
        + 0.22 * latency
        + 0.16 * token_pressure
        + 0.12 * cost
        + 0.14 * quality_pressure
        + 0.14 * max(error_rate, 1.0 if failed else 0.0)
    )
    return clamp01(pressure)


def markov_step(vector: dict[str, float], pressure: float) -> dict[str, float]:
    """Advance provider state probabilities by one Markov step with pressure bias."""
    stepped = {state: 0.0 for state in MARKOV_STATES}
    for source, probability in vector.items():
        for target, transition in MARKOV_TRANSITIONS[source].items():
            stepped[target] += probability * transition
    if pressure:
        stepped["healthy"] *= 1.0 - 0.55 * pressure
        stepped["warming"] += 0.20 * pressure
        stepped["overloaded"] += 0.45 * pressure
        stepped["failing"] += 0.25 * pressure
        stepped["cooldown"] += 0.10 * pressure
    total = sum(stepped.values()) or 1.0
    return {state: stepped[state] / total for state in MARKOV_STATES}


def markov_health_for_provider(provider: str, records: list[dict[str, Any]], decay: float) -> dict[str, Any]:
    """Predict the current provider state from recent routing observations."""
    vector = dict(MARKOV_PRIOR)
    observations = [
        item
        for item in records
        if item.get("codex_provider") == provider or item.get("attempt_provider") == provider
    ]
    for item in observations:
        pressure = provider_observation_pressure(item)
        weighted_pressure = clamp01(pressure * (1.0 - decay) + pressure)
        vector = markov_step(vector, weighted_pressure)
    risk = vector["warming"] * 0.35 + vector["overloaded"] * 0.75 + vector["failing"] + vector["cooldown"] * 0.45
    state = max(MARKOV_STATES, key=lambda item: vector[item])
    return {
        "provider": provider,
        "state": state,
        "risk": round(clamp01(risk), 4),
        "score": round(clamp01(1.0 - risk), 4),
        "probabilities": {name: round(vector[name], 4) for name in MARKOV_STATES},
        "observations": len(observations),
    }


def weighted_average(parts: list[tuple[float, float]]) -> float | None:
    """Return a weighted average for available performance signals."""
    total_weight = sum(weight for _, weight in parts)
    if total_weight <= 0:
        return None
    return sum(score * weight for score, weight in parts) / total_weight


def provider_observations(provider: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return records associated with a provider name."""
    return [
        item
        for item in records
        if item.get("codex_provider") == provider or item.get("attempt_provider") == provider
    ]


def provider_observed_cost(provider: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return recent average request cost for cost-aware switching decisions."""
    values: list[float] = []
    for item in provider_observations(provider, records):
        try:
            value = float(item.get("estimated_cost_usd"))
        except (TypeError, ValueError):
            continue
        if value >= 0:
            values.append(value)
    average_cost = sum(values) / len(values) if values else None
    return {
        "average_cost_usd": round(average_cost, 8) if average_cost is not None else None,
        "cost_observations": len(values),
    }


def provider_observed_performance(provider: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Score recent provider utility from latency, TTFT, cost, quality, and failures."""
    observations = provider_observations(provider, records)
    scores: list[float] = []
    for item in observations:
        parts: list[tuple[float, float]] = []
        if item.get("ttft_ms") is not None:
            parts.append((1.0 - metric_pressure(item.get("ttft_ms"), 800, 6_000), 0.24))
        if item.get("latency_ms") is not None:
            parts.append((1.0 - metric_pressure(item.get("latency_ms"), 5_000, 45_000), 0.24))
        if item.get("estimated_cost_usd") is not None:
            parts.append((1.0 - metric_pressure(item.get("estimated_cost_usd"), 0.005, 0.20), 0.18))
        if item.get("quality_score") is not None:
            parts.append((clamp01(float(item.get("quality_score") or 0)), 0.18))
        if item.get("error_rate") is not None:
            parts.append((1.0 - clamp01(float(item.get("error_rate") or 0)), 0.16))
        if item.get("success") is not None or item.get("returncode") is not None or item.get("error"):
            failed = (
                item.get("success") is False
                or int(item.get("returncode") or 0) != 0
                or bool(item.get("error"))
            )
            parts.append((0.0 if failed else 1.0, 0.20))
        score = weighted_average(parts)
        if score is not None:
            scores.append(clamp01(score))
    performance_score = sum(scores) / len(scores) if scores else 0.5
    return {
        "performance_score": round(clamp01(performance_score), 4),
        "performance_observations": len(scores),
    }


def adaptive_router_decision(
    fallback_order: list[str],
    policy: dict[str, Any],
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score provider fallbacks with a lightweight Markov health model."""
    config = adaptive_router_config(policy)
    records = (history if history is not None else read_history())[-int(config["max_history"]) :]
    overload_penalty = float(config["overload_penalty"])
    cold_start_penalty = float(config["cold_start_penalty"])
    performance_weight = float(config["performance_weight"])
    min_performance_observations = int(config["min_performance_observations"])
    health = {}
    for provider in fallback_order:
        provider_health = markov_health_for_provider(provider, records, float(config["decay"]))
        performance = provider_observed_performance(provider, records)
        cost = provider_observed_cost(provider, records)
        cold_start = provider_health["observations"] == 0 and provider != fallback_order[0]
        reliability_score = clamp01(
            float(provider_health["score"])
            - (float(provider_health["risk"]) * overload_penalty)
            - (cold_start_penalty if cold_start else 0.0)
        )
        has_performance = performance["performance_observations"] >= min_performance_observations
        adjusted_score = reliability_score
        if has_performance:
            adjusted_score = (
                reliability_score * (1.0 - performance_weight)
                + float(performance["performance_score"]) * performance_weight
            )
        provider_health.update(performance)
        provider_health.update(cost)
        provider_health["reliability_score"] = round(reliability_score, 4)
        provider_health["adjusted_score"] = round(clamp01(adjusted_score), 4)
        provider_health["cold_start"] = cold_start
        health[provider] = provider_health

    ranked = sorted(
        fallback_order,
        key=lambda provider: (health[provider]["adjusted_score"], -fallback_order.index(provider)),
        reverse=True,
    )
    baseline = fallback_order[0] if fallback_order else "standard"
    suggestion = ranked[0] if ranked else baseline
    confidence_delta = round(
        float(health.get(suggestion, {}).get("adjusted_score", 0))
        - float(health.get(baseline, {}).get("adjusted_score", 0)),
        4,
    )
    would_switch = suggestion != baseline and confidence_delta >= float(config["min_confidence_delta"])
    should_switch = bool(config["enabled"]) and not bool(config["shadow_mode"]) and would_switch
    baseline_cost = health.get(baseline, {}).get("average_cost_usd")
    suggestion_cost = health.get(suggestion, {}).get("average_cost_usd")
    cost_multiplier = None
    cost_guard_blocked = False
    if (
        should_switch
        and bool(config["cost_guard_enabled"])
        and isinstance(baseline_cost, int | float)
        and isinstance(suggestion_cost, int | float)
        and baseline_cost > 0
    ):
        cost_multiplier = round(float(suggestion_cost) / float(baseline_cost), 4)
        baseline_risk = float(health.get(baseline, {}).get("risk", 0))
        cost_guard_blocked = (
            cost_multiplier > float(config["max_cost_multiplier"])
            and baseline_risk < float(config["critical_risk_threshold"])
        )
        if cost_guard_blocked:
            should_switch = False
    effective_order = ranked if should_switch else fallback_order
    return {
        "enabled": bool(config["enabled"]),
        "shadow_mode": bool(config["shadow_mode"]),
        "baseline_provider": baseline,
        "suggested_provider": suggestion,
        "confidence_delta": confidence_delta,
        "effective_order": effective_order,
        "would_switch": would_switch,
        "applied": should_switch,
        "cost_guard_blocked": cost_guard_blocked,
        "cost_multiplier": cost_multiplier,
        "max_cost_multiplier": float(config["max_cost_multiplier"]),
        "health": health,
    }


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
        return HF_DIRECT_MODEL
    if provider == "standard" and model in {SMALL_LOCAL_MODEL, PHI_LOCAL_MODEL, QWEN_LOCAL_MODEL}:
        return model
    if provider == "standard":
        return "codex default"
    return model


def codex_provider_ready(provider: str) -> tuple[bool, str]:
    """Check local prerequisites for a Codex-facing provider."""
    if provider == "standard":
        return True, "standard Codex path is always available when Codex CLI exists."
    if provider == "huggingface":
        return hf_available(), "HF_TOKEN is required for the cost-routing-hf Codex profile."
    return proxy_available(), "LiteLLM OSS proxy is not listening on http://localhost:4000."


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


def run_ollama_local(prompt: str, max_output_tokens: int, ollama_model: str, label: str) -> int:
    """Call a local Ollama model without requiring the LiteLLM proxy."""
    payload = {
        "model": ollama_model,
        "messages": [
            {"role": "system", "content": "You are a concise local coding assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": max_output_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        OLLAMA_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Local {label} call failed: {exc}", file=sys.stderr)
        return 7
    elapsed = max(time.perf_counter() - started, 0.001)
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = str(message.get("content") or "").strip()
    if content:
        print(content)
    usage = data.get("usage") or {}
    completion_tokens = int(usage.get("completion_tokens") or 0)
    if completion_tokens:
        print(
            f"\n[local-{label}] completion_tokens={completion_tokens} "
            f"elapsed_s={elapsed:.2f} tokens_per_s={completion_tokens / elapsed:.2f}"
        )
    return 0


def run_phi_local(prompt: str, max_output_tokens: int) -> int:
    """Call local Phi-4 Mini through Ollama without requiring the LiteLLM proxy."""
    return run_ollama_local(prompt, max_output_tokens, PHI_OLLAMA_MODEL, "phi")


def run_qwen_local(prompt: str, max_output_tokens: int) -> int:
    """Call local Qwen through Ollama without requiring the LiteLLM proxy."""
    return run_ollama_local(prompt, max_output_tokens, QWEN_OLLAMA_MODEL, "qwen")


def route_model(
    prompt: str,
    force_model: str | None = None,
    provider: str = "auto",
) -> tuple[str, str]:
    """Choose a LiteLLM model alias."""
    if force_model:
        return force_model, "model forced by CLI option"
    complexity, reason = classify_complexity(prompt)
    normalized = normalize_for_matching(prompt)
    wants_hf = any(term in normalized for term in HF_TERMS)
    wants_long_context = any(term in normalized for term in LONG_CONTEXT_TERMS)
    wants_claude = any(term in normalized for term in CLAUDE_TERMS)

    if provider == "huggingface":
        if hf_available():
            model = HF_CHEAP_MODEL if complexity == "simple" else HF_FAST_MODEL
            return model, f"huggingface provider requested; {reason}"
        return DEFAULT_MODEL, "huggingface requested but HF_TOKEN is missing; using default OpenAI/Gemini tier"

    if provider in {"local-small", "phi"}:
        if phi_available():
            return SMALL_LOCAL_MODEL, (
                f"local small-task provider requested; capped at {SMALL_TASK_MAX_OUTPUT_TOKENS} "
                f"output tokens to target >= {SMALL_TASK_TARGET_TOKENS_PER_SECOND:.1f} tok/s; {reason}"
            )
        if qwen_available():
            return QWEN_LOCAL_MODEL, f"local small-task provider requested; Phi unavailable so Qwen selected; {reason}"
        return LIGHT_MODEL, "local small-task provider requested but Ollama is not listening; using light remote tier"

    if provider == "qwen":
        if qwen_available():
            return QWEN_LOCAL_MODEL, f"qwen provider requested; {reason}"
        return DEFAULT_MODEL, "qwen requested but Ollama is not listening on 127.0.0.1:11434; using default OpenAI/Gemini tier"

    if provider == "claude":
        if claude_available() and proxy_available():
            return CLAUDE_COMPLEX_MODEL, f"claude provider requested through active LiteLLM proxy; {reason}"
        if claude_available():
            return DEEP_MODEL, "claude requested but LiteLLM proxy is inactive; using default deep Codex tier"
        return DEEP_MODEL, "claude requested but ANTHROPIC_API_KEY is missing; using default deep Codex tier"

    if provider == "no-openai":
        if qwen_available():
            return NO_OPENAI_MODEL, f"OpenAI avoided; Gemini/Qwen alias selected; {reason}"
        return LONG_MODEL, f"OpenAI avoided; Qwen unavailable so Gemini long-context alias selected; {reason}"

    if provider == "openai":
        model = LIGHT_MODEL if complexity == "simple" else DEEP_MODEL
        return model, f"openai provider requested; {reason}"

    if provider == "gemini":
        model = LIGHT_MODEL if complexity == "simple" and not wants_long_context else LONG_MODEL
        return model, f"gemini provider requested; {reason}"

    if wants_hf and hf_available():
        model = HF_CHEAP_MODEL if complexity == "simple" else HF_FAST_MODEL
        return model, f"huggingface-related task; {reason}"

    if any(term in normalized for term in QWEN_TERMS) and qwen_available():
        return QWEN_LOCAL_MODEL, f"qwen local task; {reason}"

    if wants_claude and claude_available() and proxy_available():
        return CLAUDE_COMPLEX_MODEL, f"claude-related task through active LiteLLM proxy; {reason}"

    if wants_long_context:
        return LONG_MODEL, f"long-context task; {reason}"

    if complexity == "simple":
        model = LIGHT_MODEL
    elif complexity == "complex":
        model = DEEP_MODEL
    else:
        model = DEFAULT_MODEL
    return model, reason


def build_optimized_prompt(prompt: str, max_input_tokens: int) -> str:
    """Apply context cleanup, log compression, and intelligent truncation."""
    return smart_truncate(clean_text(compress_logs(prompt)), max_input_tokens)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate request cost from editable placeholder deployment rates."""
    rates = ESTIMATED_RATES[model]
    return round(
        (input_tokens / 1_000_000) * rates["input"]
        + (output_tokens / 1_000_000) * rates["output"],
        8,
    )


def enable_router() -> int:
    """Install the optional profile while preserving all existing Codex settings."""
    ensure_directories()
    config = read_text(CODEX_CONFIG)
    if BEGIN_MARKER not in config and CODEX_CONFIG.exists():
        shutil.copyfile(CODEX_CONFIG, CONFIG_BACKUP)
    config = remove_profile_block(config)
    updated = config.rstrip() + ("\n\n" if config.strip() else "") + PROFILE_BLOCK
    write_text(CODEX_CONFIG, updated)
    save_state(enabled=True, enabled_at=utc_now(), current_model=DEFAULT_MODEL)
    print("Cost routing enabled.")
    print("LiteLLM OSS profile installed: cost-routing")
    print("Optional Hugging Face profile installed: cost-routing-hf")
    print("Start the profile with:")
    print("  codex --profile cost-routing")
    print("  codex --profile cost-routing-hf")
    print("Use optimized one-shot routing with:")
    print('  python codex_cost_router.py run "your task"')
    return 0


def disable_router() -> int:
    """Remove only the installed profile and plugin fragment."""
    ensure_directories()
    if CONFIG_BACKUP.exists():
        shutil.copyfile(CONFIG_BACKUP, CODEX_CONFIG)
        CONFIG_BACKUP.unlink()
    else:
        write_text(CODEX_CONFIG, remove_profile_block(read_text(CODEX_CONFIG)))
    save_state(enabled=False, disabled_at=utc_now())
    print("Cost routing disabled. Existing Codex configuration was preserved.")
    return 0


def router_enabled() -> bool:
    """Check that both managed profile markers exist."""
    config = read_text(CODEX_CONFIG)
    return BEGIN_MARKER in config and END_MARKER in config


def print_status() -> int:
    """Display router state and the latest routing decision."""
    state = load_state()
    history = read_history()
    latest = history[-1] if history else {}
    print("Codex Cost Router")
    print("-----------------")
    print(f"Profile active     : {'yes' if router_enabled() else 'no'}")
    print(f"Current model      : {latest.get('model', state.get('current_model', DEFAULT_MODEL))}")
    print(f"Codex profile      : {latest.get('codex_profile', 'none')}")
    print(f"Last estimated cost: ${latest.get('estimated_cost_usd', 0):.8f}")
    print(f"Last routing       : {latest.get('routing_reason', 'none')}")
    print(f"Execution mode     : {latest.get('execution_mode', 'none')}")
    return 0


def print_history(limit: int) -> int:
    """Display recent routing records as a compact table."""
    records = read_history()[-limit:]
    print("Timestamp                  Model          Input  Output  Ratio   Estimated USD")
    print("-------------------------  -------------  -----  ------  ------  -------------")
    for item in records:
        print(
            f"{item.get('timestamp', '')[:25]:25}  "
            f"{item.get('model', ''):13}  "
            f"{item.get('estimated_input_tokens', 0):5}  "
            f"{item.get('estimated_output_tokens', 0):6}  "
            f"{item.get('compression_ratio', 0):6.2f}  "
            f"${item.get('estimated_cost_usd', 0):.8f}"
        )
    return 0


def print_stats() -> int:
    """Display aggregate estimated routing statistics."""
    records = read_history()
    if not records:
        print("No routing history yet.")
        return 0
    total_cost = sum(float(item.get("estimated_cost_usd", 0)) for item in records)
    total_savings = sum(float(item.get("estimated_savings_usd", 0)) for item in records)
    original = sum(int(item.get("original_input_tokens", 0)) for item in records)
    optimized = sum(int(item.get("estimated_input_tokens", 0)) for item in records)
    print("Codex Cost Router statistics")
    print("----------------------------")
    print(f"Requests routed          : {len(records)}")
    print(f"Original input tokens    : {original}")
    print(f"Optimized input tokens   : {optimized}")
    print(f"Tokens removed           : {max(0, original - optimized)}")
    print(f"Estimated routed cost    : ${total_cost:.8f}")
    adaptive_records = [item for item in records if isinstance(item.get("adaptive_router"), dict)]
    switches = sum(1 for item in adaptive_records if item["adaptive_router"].get("would_switch"))
    applied = sum(1 for item in adaptive_records if item["adaptive_router"].get("applied"))
    print(f"Estimated savings vs strong: ${total_savings:.8f}")
    if adaptive_records:
        print(f"Adaptive observations   : {len(adaptive_records)}")
        print(f"Adaptive would switch   : {switches}")
        print(f"Adaptive applied switch : {applied}")
    print()
    return print_history(10)


def find_codex() -> str | None:
    """Locate Codex CLI without assuming a specific Windows installation path."""
    return shutil.which("codex") or os.environ.get("CODEX_CLI_PATH")


def find_litellm() -> str | None:
    """Locate LiteLLM CLI, including the documented short-path Windows venv."""
    configured = os.environ.get("LITELLM_CLI_PATH")
    if configured and Path(configured).is_file():
        return configured
    discovered = shutil.which("litellm")
    if discovered:
        return discovered
    if WINDOWS_LITELLM_FALLBACK.is_file():
        return str(WINDOWS_LITELLM_FALLBACK)
    return None


def proxy_available() -> bool:
    """Check whether the local LiteLLM OSS proxy is accepting TCP connections."""
    try:
        with socket.create_connection((LITELLM_HOST, LITELLM_PORT), timeout=1):
            return True
    except OSError:
        return False


def print_doctor() -> int:
    """Display local setup checks without printing secret values."""
    checks = [
        ("Codex CLI", bool(find_codex()), find_codex() or "not found"),
        ("Standard Codex path", True, "default work path; no proxy required"),
        ("LiteLLM command optional", True, find_litellm() or "not found; proxy dispatch disabled"),
        (
            "LiteLLM proxy optional",
            True,
            "listening for Gemini/Phi/Qwen/Claude aliases" if proxy_available() else "inactive; standard Codex remains usable",
        ),
        (
            "Gemini dispatch optional",
            True,
            "ready through proxy" if proxy_available() and os.environ.get("GEMINI_API_KEY") else "needs active proxy + GEMINI_API_KEY",
        ),
        (
            "Ollama Phi small-task optional",
            True,
            "listening; small tasks can use Phi-4 Mini"
            if phi_available()
            else "missing; run ollama pull phi4-mini and start Ollama",
        ),
        (
            "Ollama Qwen optional",
            True,
            "listening on 127.0.0.1:11434" if qwen_available() else "missing; run Start-CodexQwenOllama.ps1",
        ),
        (
            "Claude complex optional",
            True,
            "ready through proxy" if proxy_available() and claude_available() else "needs active proxy + ANTHROPIC_API_KEY",
        ),
        ("HF_TOKEN optional", True, "set" if hf_available() else "missing; Hugging Face aliases disabled"),
        ("PYTHONUTF8 optional", True, "1" if os.environ.get("PYTHONUTF8") == "1" else "not forced"),
        ("Cost-routing profile optional", True, "enabled" if router_enabled() else "disabled"),
    ]
    print("Codex Cost Router doctor")
    print("------------------------")
    for name, passed, detail in checks:
        print(f"{'OK' if passed else 'FIX':3}  {name:30} {detail}")
    if not proxy_available():
        print("\nLiteLLM is optional. Start it only when you want Gemini/Claude/API dispatch:")
        executable = find_litellm() or "litellm"
        print(f"  & '{executable}' --config .\\scripts\\python\\litellm-cost-routing.yaml --port 4000")
    return 0 if all(passed for _, passed, _ in checks) else 1


def run_router(args: argparse.Namespace) -> int:
    """Optimize, log, and optionally execute a one-shot Codex CLI request."""
    prompt = " ".join(args.prompt).strip()
    optimized = build_optimized_prompt(prompt, args.max_input_tokens)
    policy = load_policy(args.policy)
    selected_codex_provider, codex_provider_reason = codex_provider_from_policy(args.codex_provider, policy)
    selected_provider, provider_reason = provider_from_policy(prompt, args.provider, policy)
    effective_provider = (
        "huggingface"
        if selected_codex_provider == "huggingface" and selected_provider == "auto"
        else selected_provider
    )
    model, reason = route_model(prompt, args.force_model, effective_provider)
    fallback_order = fallback_order_from_policy(selected_codex_provider, policy)
    adaptive_decision = adaptive_router_decision(fallback_order, policy)
    fallback_order = list(adaptive_decision["effective_order"])
    active_codex_provider = fallback_order[0] if fallback_order else selected_codex_provider
    selected_codex_profile = codex_profile(active_codex_provider)
    selected_codex_model = codex_model(model, active_codex_provider)
    original_tokens = estimate_tokens(prompt)
    input_tokens = estimate_tokens(optimized)
    output_tokens = (
        min(args.max_output_tokens, SMALL_TASK_MAX_OUTPUT_TOKENS)
        if model in {SMALL_LOCAL_MODEL, PHI_LOCAL_MODEL}
        else args.max_output_tokens
    )
    compression_ratio = round(input_tokens / max(1, original_tokens), 4)
    cost = estimate_cost(model, input_tokens, output_tokens)
    max_cost = float(policy.get("max_cost_usd") or 0)
    strong_cost = estimate_cost(DEFAULT_MODEL, input_tokens, output_tokens)
    execution_mode = "dry-run" if args.dry_run else "codex-exec"

    record = {
        "timestamp": utc_now(),
        "model": model,
        "provider": effective_provider,
        "provider_reason": provider_reason,
        "codex_provider": active_codex_provider,
        "requested_codex_provider": selected_codex_provider,
        "codex_provider_reason": codex_provider_reason,
        "codex_profile": selected_codex_profile,
        "codex_model": selected_codex_model,
        "fallback_order": fallback_order,
        "adaptive_router": {
            "enabled": adaptive_decision["enabled"],
            "shadow_mode": adaptive_decision["shadow_mode"],
            "baseline_provider": adaptive_decision["baseline_provider"],
            "suggested_provider": adaptive_decision["suggested_provider"],
            "confidence_delta": adaptive_decision["confidence_delta"],
            "would_switch": adaptive_decision["would_switch"],
            "applied": adaptive_decision["applied"],
            "cost_guard_blocked": adaptive_decision["cost_guard_blocked"],
            "cost_multiplier": adaptive_decision["cost_multiplier"],
            "max_cost_multiplier": adaptive_decision["max_cost_multiplier"],
            "health": adaptive_decision["health"],
        },
        "original_input_tokens": original_tokens,
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "compression_ratio": compression_ratio,
        "routing_reason": reason,
        "execution_mode": execution_mode,
        "estimated_cost_usd": cost,
        "policy_max_cost_usd": max_cost,
        "estimated_savings_usd": round(max(0.0, strong_cost - cost), 8),
    }
    append_log(record)
    save_state(current_model=model, last_routing=record)

    print(f"Model             : {model}")
    print(f"Provider          : {effective_provider}")
    print(f"Codex profile     : {selected_codex_profile}")
    print(f"Codex model       : {selected_codex_model}")
    print(f"Fallback order    : {', '.join(fallback_order)}")
    if adaptive_decision["enabled"]:
        print(
            "Adaptive router   : "
            f"{'applied' if adaptive_decision['applied'] else 'shadow'} "
            f"{adaptive_decision['baseline_provider']} -> {adaptive_decision['suggested_provider']} "
            f"(delta={adaptive_decision['confidence_delta']:.2f})"
        )
        if adaptive_decision["cost_guard_blocked"]:
            print(
                "Cost guard        : blocked expensive switch "
                f"(x{adaptive_decision['cost_multiplier']:.2f} > "
                f"x{adaptive_decision['max_cost_multiplier']:.2f})"
            )
    print(f"Routing reason    : {reason}")
    print(f"Input tokens      : {original_tokens} -> {input_tokens}")
    print(f"Compression ratio : {compression_ratio:.2f}")
    print(f"Output budget     : {output_tokens}")
    print(f"Estimated cost    : ${cost:.8f}")
    print(f"Proxy active      : {'yes' if proxy_available() else 'no'}")
    print(f"Phi small local   : {'yes' if phi_available() else 'no'}")
    print(f"Qwen local        : {'yes' if qwen_available() else 'no'}")
    if model in {SMALL_LOCAL_MODEL, PHI_LOCAL_MODEL}:
        print(
            "Small-task target : "
            f">= {SMALL_TASK_TARGET_TOKENS_PER_SECOND:.1f} tok/s with <= {SMALL_TASK_MAX_OUTPUT_TOKENS} output tokens"
        )
    if max_cost > 0 and cost > max_cost:
        print(f"Policy cost limit : ${max_cost:.8f} exceeded")

    if args.dry_run:
        print("\nOptimized prompt:")
        print(optimized)
        return 0

    codex = find_codex()
    if not codex:
        print("Codex CLI was not found in PATH or CODEX_CLI_PATH.", file=sys.stderr)
        return 3

    last_returncode = 0
    for attempt_provider in fallback_order:
        ready, message = codex_provider_ready(attempt_provider)
        if not ready:
            print(f"Skipping {attempt_provider}: {message}", file=sys.stderr)
            last_returncode = 5 if attempt_provider == "huggingface" else 4
            continue
        if attempt_provider != "standard" and not router_enabled():
            print(
                f"Skipping {attempt_provider}: managed Codex profile is not enabled.",
                file=sys.stderr,
            )
            last_returncode = 4
            continue
        if attempt_provider == "standard" and model in {SMALL_LOCAL_MODEL, PHI_LOCAL_MODEL} and phi_available():
            print("Executing through local Ollama Phi-4 Mini (no LiteLLM proxy required)")
            return run_phi_local(optimized, output_tokens)
        if attempt_provider == "standard" and model == QWEN_LOCAL_MODEL and qwen_available():
            print("Executing through local Ollama Qwen (no LiteLLM proxy required)")
            return run_qwen_local(optimized, output_tokens)
        attempt_profile = codex_profile(attempt_provider)
        attempt_model = codex_model(model, attempt_provider)
        print(f"Executing through {attempt_profile} ({attempt_model})")
        command = build_codex_command(
            codex,
            attempt_provider,
            model,
            args.codex_arg,
            optimized,
        )
        last_returncode = subprocess.run(command, check=False).returncode
        if last_returncode == 0:
            return 0
        print(f"Provider {attempt_provider} failed with exit code {last_returncode}.", file=sys.stderr)
    return last_returncode or 6


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("enable", help="Install the optional Codex profile.")
    subparsers.add_parser("disable", help="Remove the optional Codex profile.")
    subparsers.add_parser("status", help="Show activation and latest routing status.")
    subparsers.add_parser("doctor", help="Check Codex, LiteLLM, keys, proxy, and profile.")
    subparsers.add_parser("stats", help="Show aggregate estimated savings.")

    history = subparsers.add_parser("history", help="Show recent routing history.")
    history.add_argument("--limit", type=int, default=10)

    run = subparsers.add_parser("run", help="Optimize a prompt and call Codex CLI.")
    run.add_argument("prompt", nargs="+", help="Prompt sent to Codex after optimization.")
    run.add_argument("--dry-run", action="store_true", help="Show routing without calling Codex.")
    run.add_argument("--force-model", choices=MODELS)
    run.add_argument(
        "--policy",
        type=Path,
        default=POLICY_FILE,
        help="Routing policy YAML file.",
    )
    run.add_argument(
        "--provider",
        choices=PROVIDERS,
        default=None,
        help="Provider preference behind LiteLLM. Can also be set with CODEX_ROUTER_PROVIDER.",
    )
    run.add_argument(
        "--codex-provider",
        choices=CODEX_PROVIDERS,
        default=None,
        help=(
            "Codex-facing provider path: auto chooses LiteLLM when active, "
            "standard uses normal Codex, litellm uses the local proxy, and "
            "huggingface uses the optional direct HF layer."
        ),
    )
    run.add_argument("--max-input-tokens", type=int, default=DEFAULT_MAX_INPUT_TOKENS)
    run.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    run.add_argument(
        "--codex-arg",
        action="append",
        default=[],
        help="Additional Codex exec argument. Repeat once per argument.",
    )
    return parser


def normalize_legacy_flags(argv: list[str]) -> list[str]:
    """Accept the requested --enable, --disable, and --status convenience flags."""
    aliases = {"--enable": "enable", "--disable": "disable", "--status": "status"}
    if argv and argv[0] in aliases:
        return [aliases[argv[0]], *argv[1:]]
    return argv


def main(argv: list[str] | None = None) -> int:
    """Run the selected router command."""
    args = build_parser().parse_args(normalize_legacy_flags(argv or sys.argv[1:]))
    if args.command == "enable":
        return enable_router()
    if args.command == "disable":
        return disable_router()
    if args.command == "status":
        return print_status()
    if args.command == "stats":
        return print_stats()
    if args.command == "doctor":
        return print_doctor()
    if args.command == "history":
        return print_history(args.limit)
    return run_router(args)


if __name__ == "__main__":
    raise SystemExit(main())
