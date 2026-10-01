import json
import math
import random
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


from risk_router_config import (
    MODEL_PROFILE, ROUTE_CANDIDATES, SOFT_WEIGHTS, TEMPERATURE, EWMA_ALPHA,
    HARD_LIMIT_STATUS_SECONDS,
)

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "risk-router-state.json"
STATE_LOCK = threading.Lock()
IN_FLIGHT_LOCK = threading.Lock()
IN_FLIGHT: dict[str, int] = defaultdict(int)


@dataclass
class Choice:
    model: str
    risk: float
    probability: float
    hard_limited: bool = False
    hard_limit_reason: str | None = None
    in_flight: int = 0


def now() -> float:
    return time.time()


def load_state_unlocked() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"models": {}, "requests": []}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"models": {}, "requests": []}


def load_state() -> dict[str, Any]:
    with STATE_LOCK:
        return load_state_unlocked()


def save_state_unlocked(state: dict[str, Any]) -> None:
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE_PATH)


def save_state(state: dict[str, Any]) -> None:
    with STATE_LOCK:
        save_state_unlocked(state)


def update_state(mutator: Any) -> dict[str, Any]:
    with STATE_LOCK:
        state = load_state_unlocked()
        mutator(state)
        save_state_unlocked(state)
        return state


def profile_for(model: str) -> dict[str, float]:
    return MODEL_PROFILE.get(
        model,
        {
            "cost": 0.30,
            "total_latency": 6000.0,
            "ttft": 1500.0,
            "tokens_per_second": 25.0,
            "tpm_limit": 250_000,
            "max_in_flight": 1,
        },
    )


def ensure_model_state(state: dict[str, Any], model: str) -> dict[str, Any]:
    models = state.setdefault("models", {})
    if model not in models:
        profile = profile_for(model)
        models[model] = {
            "ewma_cost": profile["cost"],
            "ewma_latency_ms": profile["total_latency"],
            "ewma_total_latency_ms": profile["total_latency"],
            "ewma_ttft_ms": profile["ttft"],
            "ewma_tokens_per_second": profile["tokens_per_second"],
            "ewma_queue_depth": 0.0,
            "ewma_error_rate": 0.0,
            "ewma_token_pressure": 0.0,
            "ewma_response_tokens": 0.0,
            "hard_limited_until": 0.0,
            "hard_limit_reason": None,
            "last_status": None,
            "last_error": None,
            "last_used_at": None,
            "calls": 0,
            "successes": 0,
            "failures": 0,
        }
    return models[model]


def ewma(old: float, sample: float) -> float:
    return (EWMA_ALPHA * sample) + ((1.0 - EWMA_ALPHA) * old)


def normalize(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    if math.isclose(lo, hi):
        return {key: 0.0 for key in values}
    return {key: (value - lo) / (hi - lo) for key, value in values.items()}


def get_in_flight(model: str) -> int:
    with IN_FLIGHT_LOCK:
        return int(IN_FLIGHT.get(model, 0))


def acquire_in_flight(model: str) -> int:
    with IN_FLIGHT_LOCK:
        current = int(IN_FLIGHT.get(model, 0))
        IN_FLIGHT[model] = current + 1
        return current


def release_in_flight(model: str) -> None:
    with IN_FLIGHT_LOCK:
        IN_FLIGHT[model] = max(0, int(IN_FLIGHT.get(model, 0)) - 1)


def hard_limit_for(state: dict[str, Any], model: str) -> str | None:
    metrics = ensure_model_state(state, model)
    until = float(metrics.get("hard_limited_until") or 0.0)
    if until > now():
        reason = str(metrics.get("hard_limit_reason") or "cooldown")
        return f"{reason}; {int(until - now())}s remaining"

    profile = profile_for(model)
    in_flight = get_in_flight(model)
    max_in_flight = int(profile.get("max_in_flight", 1))
    if in_flight >= max_in_flight:
        return f"in_flight {in_flight}/{max_in_flight}"
    return None


def soft_risks_for(state: dict[str, Any], candidates: list[str]) -> dict[str, float]:
    cost = {}
    ttft = {}
    total_latency = {}
    generation_slowness = {}
    errors = {}
    token_pressure = {}
    queue = {}
    for model in candidates:
        metrics = ensure_model_state(state, model)
        cost[model] = float(metrics["ewma_cost"])
        ttft[model] = float(metrics["ewma_ttft_ms"])
        total_latency[model] = float(metrics["ewma_total_latency_ms"])
        generation_slowness[model] = -max(0.01, float(metrics["ewma_tokens_per_second"]))
        errors[model] = float(metrics["ewma_error_rate"])
        token_pressure[model] = float(metrics["ewma_token_pressure"])
        queue[model] = max(float(metrics.get("ewma_queue_depth", 0.0)), float(get_in_flight(model)))

    n_cost = normalize(cost)
    n_ttft = normalize(ttft)
    n_total_latency = normalize(total_latency)
    n_generation_slowness = normalize(generation_slowness)
    n_queue = normalize(queue)
    out = {}
    for model in candidates:
        out[model] = (
            SOFT_WEIGHTS["cost"] * n_cost[model]
            + SOFT_WEIGHTS["ttft"] * n_ttft[model]
            + SOFT_WEIGHTS["total_latency"] * n_total_latency[model]
            + SOFT_WEIGHTS["tokens_per_second"] * n_generation_slowness[model]
            + SOFT_WEIGHTS["error"] * errors[model]
            + SOFT_WEIGHTS["token_pressure"] * token_pressure[model]
            + SOFT_WEIGHTS["queue"] * n_queue[model]
        )
    return out


def choose_model(state: dict[str, Any], requested_model: str) -> tuple[str, list[Choice]]:
    candidates = ROUTE_CANDIDATES.get(requested_model)
    if not candidates:
        return requested_model, []

    hard_reasons = {model: hard_limit_for(state, model) for model in candidates}
    eligible = [model for model in candidates if not hard_reasons[model]]
    all_hard_limited = not eligible
    scoring_candidates = eligible if eligible else candidates
    risks = soft_risks_for(state, scoring_candidates)
    scores = {model: math.exp(-risk / max(TEMPERATURE, 0.01)) for model, risk in risks.items()}
    total = sum(scores.values()) or 1.0
    probabilities = {model: scores[model] / total for model in scoring_candidates}

    draw = random.random()
    cumulative = 0.0
    selected = scoring_candidates[-1]
    for model in scoring_candidates:
        cumulative += probabilities[model]
        if draw <= cumulative:
            selected = model
            break

    choices = []
    for model in candidates:
        hard_reason = hard_reasons[model]
        choices.append(
            Choice(
                model=model,
                risk=risks.get(model, 1_000_000.0),
                probability=probabilities.get(model, 0.0),
                hard_limited=bool(hard_reason) and not all_hard_limited,
                hard_limit_reason=hard_reason,
                in_flight=get_in_flight(model),
            )
        )
    choices.sort(key=lambda item: (item.hard_limited, item.risk))
    return selected, choices


def estimate_prompt_tokens(payload: dict[str, Any]) -> int:
    text = ""
    for message in payload.get("messages", []):
        text += str(message.get("content", "")) + " "
    return max(1, len(text) // 4 + int(payload.get("max_tokens") or 0))


def extract_completion_tokens(body: bytes) -> int:
    try:
        data = json.loads(body.decode("utf-8"))
        usage = data.get("usage") or {}
        if usage.get("completion_tokens") is not None:
            return max(0, int(usage["completion_tokens"]))
        choices = data.get("choices") or []
        text = ""
        for choice in choices:
            message = choice.get("message") or {}
            text += str(message.get("content") or "")
        return max(1, len(text) // 4) if text else 0
    except Exception:
        return 0


def update_metrics(
    state: dict[str, Any],
    model: str,
    ok: bool,
    status: int,
    total_latency_ms: float,
    ttft_ms: float,
    tokens_per_second: float,
    prompt_token_estimate: int,
    response_tokens: int,
    queue_depth: int,
    error: str | None,
) -> None:
    metrics = ensure_model_state(state, model)
    profile = profile_for(model)
    metrics["calls"] += 1
    metrics["successes"] += 1 if ok else 0
    metrics["failures"] += 0 if ok else 1
    metrics["last_status"] = status
    metrics["last_error"] = error
    metrics["last_used_at"] = now()
    metrics["ewma_latency_ms"] = ewma(float(metrics["ewma_latency_ms"]), total_latency_ms)
    metrics["ewma_total_latency_ms"] = ewma(float(metrics["ewma_total_latency_ms"]), total_latency_ms)
    metrics["ewma_ttft_ms"] = ewma(float(metrics["ewma_ttft_ms"]), ttft_ms)
    metrics["ewma_queue_depth"] = ewma(float(metrics.get("ewma_queue_depth", 0.0)), float(queue_depth))
    metrics["ewma_error_rate"] = ewma(float(metrics["ewma_error_rate"]), 0.0 if ok else 1.0)
    if ok and tokens_per_second > 0:
        metrics["ewma_tokens_per_second"] = ewma(
            float(metrics["ewma_tokens_per_second"]),
            tokens_per_second,
        )
    if ok and response_tokens > 0:
        metrics["ewma_response_tokens"] = ewma(float(metrics.get("ewma_response_tokens", 0.0)), response_tokens)

    pressure_sample = min(1.0, prompt_token_estimate / max(float(profile["tpm_limit"]), 1.0))
    if status == 429:
        pressure_sample = 1.0
    metrics["ewma_token_pressure"] = ewma(float(metrics["ewma_token_pressure"]), pressure_sample)

    if status in HARD_LIMIT_STATUS_SECONDS:
        metrics["hard_limited_until"] = now() + HARD_LIMIT_STATUS_SECONDS[status]
        metrics["hard_limit_reason"] = f"http_{status}"
    elif ok:
        metrics["hard_limited_until"] = 0.0
        metrics["hard_limit_reason"] = None


def append_request(state: dict[str, Any], event: dict[str, Any]) -> None:
    requests = state.setdefault("requests", [])
    requests.append(event)
    del requests[:-200]


def response_headers(headers: list[tuple[str, str]]) -> list[tuple[str, str]]:
    blocked = {"transfer-encoding", "connection", "content-encoding", "content-length"}
    return [(key, value) for key, value in headers if key.lower() not in blocked]


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    models = state.get("models", {})
    summary = {}
    for model, metrics in models.items():
        calls = int(metrics.get("calls", 0))
        hard_limited_until = float(metrics.get("hard_limited_until") or 0.0)
        summary[model] = {
            "calls": calls,
            "success_rate": round(float(metrics.get("successes", 0)) / calls, 4) if calls else None,
            "ewma_ttft_ms": round(float(metrics.get("ewma_ttft_ms", 0)), 2),
            "ewma_total_latency_ms": round(float(metrics.get("ewma_total_latency_ms", 0)), 2),
            "ewma_latency_ms": round(float(metrics.get("ewma_latency_ms", 0)), 2),
            "ewma_tokens_per_second": round(float(metrics.get("ewma_tokens_per_second", 0)), 2),
            "ewma_queue_depth": round(float(metrics.get("ewma_queue_depth", 0)), 2),
            "in_flight": get_in_flight(model),
            "ewma_error_rate": round(float(metrics.get("ewma_error_rate", 0)), 4),
            "ewma_token_pressure": round(float(metrics.get("ewma_token_pressure", 0)), 4),
            "ewma_response_tokens": round(float(metrics.get("ewma_response_tokens", 0)), 2),
            "hard_limited": hard_limited_until > now(),
            "hard_limited_remaining_s": max(0, int(hard_limited_until - now())),
            "hard_limit_reason": metrics.get("hard_limit_reason"),
            "last_status": metrics.get("last_status"),
            "last_error": metrics.get("last_error"),
        }
    return {
        "strategy": "hard-limits + softmax(-soft_risk/tau)",
        "soft_score_weights": SOFT_WEIGHTS,
        "temperature": TEMPERATURE,
        "hard_limits": {
            "status_cooldowns_seconds": HARD_LIMIT_STATUS_SECONDS,
            "max_in_flight": {model: int(profile["max_in_flight"]) for model, profile in MODEL_PROFILE.items()},
        },
        "models": summary,
    }
