"""LiteLLM-independent adaptive routing helpers for token pressure.

The module intentionally has no LiteLLM imports.  It scores route candidates
from plain dictionaries so it can be used by the local proxy, dry-run tooling,
or tests without depending on LiteLLM internals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


EWMA_ALPHA = 0.25
DEFAULT_RPM_WINDOW_SECONDS = 60


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def ewma(old: float, sample: float, alpha: float = EWMA_ALPHA) -> float:
    return (alpha * sample) + ((1.0 - alpha) * old)


def estimate_prompt_tokens(payload: dict[str, Any]) -> int:
    """Return a conservative token estimate for OpenAI-compatible chat bodies."""
    total_chars = 0
    for message in payload.get("messages", []):
        content = message.get("content", "")
        if isinstance(content, list):
            total_chars += sum(len(str(part.get("text", part))) for part in content)
        else:
            total_chars += len(str(content))
    max_tokens = payload.get("max_tokens") or payload.get("max_completion_tokens") or 0
    try:
        reserved = int(max_tokens)
    except (TypeError, ValueError):
        reserved = 0
    return max(1, math.ceil(total_chars / 4) + max(0, reserved))


def update_pressure_state(
    metrics: dict[str, Any],
    *,
    prompt_tokens: int,
    response_tokens: int = 0,
    status: int | None = None,
    queue_depth: int = 0,
    alpha: float = EWMA_ALPHA,
) -> dict[str, Any]:
    """Update EWMA token and request pressure metrics in-place."""
    request_tokens = max(1, int(prompt_tokens) + max(0, int(response_tokens)))
    tpm_limit = max(1.0, float(metrics.get("tpm_limit") or metrics.get("tokens_per_minute") or 250_000))
    rpm_limit = max(1.0, float(metrics.get("rpm_limit") or metrics.get("requests_per_minute") or 60))

    prior_tpm = float(metrics.get("ewma_tpm") or 0.0)
    prior_rpm = float(metrics.get("ewma_rpm") or 0.0)
    metrics["ewma_tpm"] = ewma(prior_tpm, float(request_tokens), alpha)
    metrics["ewma_rpm"] = ewma(prior_rpm, 1.0, alpha)
    metrics["ewma_queue_depth"] = ewma(float(metrics.get("ewma_queue_depth") or 0.0), float(queue_depth), alpha)

    token_pressure = clamp01(float(metrics["ewma_tpm"]) / tpm_limit)
    rpm_pressure = clamp01(float(metrics["ewma_rpm"]) / rpm_limit)
    if status == 429:
        token_pressure = 1.0
        rpm_pressure = max(rpm_pressure, 0.85)
    metrics["ewma_token_pressure"] = ewma(float(metrics.get("ewma_token_pressure") or 0.0), token_pressure, alpha)
    metrics["ewma_rpm_pressure"] = ewma(float(metrics.get("ewma_rpm_pressure") or 0.0), rpm_pressure, alpha)
    return metrics


def estimate_tpm_rpm_risk(
    *,
    prompt_tokens: int,
    response_tokens: int = 0,
    in_flight: int = 0,
    tpm_limit: float = 250_000,
    rpm_limit: float = 60,
    observed_tpm: float = 0.0,
    observed_rpm: float = 0.0,
) -> dict[str, float]:
    """Estimate near-term quota pressure for one candidate route."""
    request_tokens = max(1, int(prompt_tokens) + max(0, int(response_tokens)))
    projected_tpm = max(0.0, observed_tpm) + request_tokens * (1 + max(0, in_flight))
    projected_rpm = max(0.0, observed_rpm) + 1 + max(0, in_flight)
    tpm_pressure = clamp01(projected_tpm / max(float(tpm_limit), 1.0))
    rpm_pressure = clamp01(projected_rpm / max(float(rpm_limit), 1.0))
    risk = clamp01((0.65 * tpm_pressure) + (0.35 * rpm_pressure))
    return {
        "projected_tpm": round(projected_tpm, 4),
        "projected_rpm": round(projected_rpm, 4),
        "tpm_pressure": round(tpm_pressure, 4),
        "rpm_pressure": round(rpm_pressure, 4),
        "quota_risk": round(risk, 4),
    }


def markov_overload_risk(metrics: dict[str, Any]) -> float:
    """Return a small Markov-inspired overload score from previous state."""
    prior = clamp01(float(metrics.get("markov_overloaded") or 0.0))
    pressure = clamp01(
        0.55 * float(metrics.get("ewma_token_pressure") or 0.0)
        + 0.30 * float(metrics.get("ewma_rpm_pressure") or 0.0)
        + 0.15 * float(metrics.get("ewma_error_rate") or 0.0)
    )
    return clamp01((0.72 * prior) + (0.28 * pressure))


@dataclass(frozen=True)
class RouteScore:
    model: str
    score: float
    quota_risk: float
    cost_risk: float
    latency_risk: float
    error_risk: float
    markov_risk: float
    dry_run: bool = False


def score_route(
    model: str,
    metrics: dict[str, Any],
    *,
    prompt_tokens: int,
    response_tokens: int = 0,
    in_flight: int = 0,
    dry_run: bool = False,
    weights: dict[str, float] | None = None,
) -> RouteScore:
    """Score one model candidate; lower score is better."""
    quota = estimate_tpm_rpm_risk(
        prompt_tokens=prompt_tokens,
        response_tokens=response_tokens,
        in_flight=in_flight,
        tpm_limit=float(metrics.get("tpm_limit") or 250_000),
        rpm_limit=float(metrics.get("rpm_limit") or 60),
        observed_tpm=float(metrics.get("ewma_tpm") or 0.0),
        observed_rpm=float(metrics.get("ewma_rpm") or 0.0),
    )
    cost_risk = clamp01(float(metrics.get("cost") or metrics.get("ewma_cost") or 0.0) / 1.0)
    latency_risk = clamp01(float(metrics.get("ewma_total_latency_ms") or metrics.get("total_latency") or 0.0) / 45_000)
    error_risk = clamp01(float(metrics.get("ewma_error_rate") or 0.0))
    markov_risk = markov_overload_risk(metrics)
    selected_weights = weights or {
        "quota": 0.34,
        "cost": 0.20,
        "latency": 0.18,
        "error": 0.18,
        "markov": 0.10,
    }
    score = (
        selected_weights["quota"] * quota["quota_risk"]
        + selected_weights["cost"] * cost_risk
        + selected_weights["latency"] * latency_risk
        + selected_weights["error"] * error_risk
        + selected_weights["markov"] * markov_risk
    )
    return RouteScore(
        model=model,
        score=round(clamp01(score), 4),
        quota_risk=float(quota["quota_risk"]),
        cost_risk=round(cost_risk, 4),
        latency_risk=round(latency_risk, 4),
        error_risk=round(error_risk, 4),
        markov_risk=round(markov_risk, 4),
        dry_run=dry_run,
    )


def choose_adaptive_route(
    candidates: list[str],
    model_metrics: dict[str, dict[str, Any]],
    *,
    prompt_tokens: int,
    response_tokens: int = 0,
    in_flight: dict[str, int] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Rank candidates by adaptive quota, cost, latency, and reliability risk."""
    if not candidates:
        raise ValueError("At least one route candidate is required.")
    active = in_flight or {}
    scores = [
        score_route(
            model,
            model_metrics.get(model, {}),
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            in_flight=int(active.get(model, 0)),
            dry_run=dry_run,
        )
        for model in candidates
    ]
    ranked = sorted(scores, key=lambda item: (item.score, candidates.index(item.model)))
    return {
        "selected_model": ranked[0].model,
        "dry_run": dry_run,
        "scores": [item.__dict__ for item in ranked],
    }
