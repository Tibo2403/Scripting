"""Codex cost router: adaptive responsibilities."""

from __future__ import annotations
from typing import Any

import codex_router_config as router_config
import codex_router_storage as router_storage


def truthy(value: Any) -> bool:
    """Parse policy booleans from Python or YAML-like scalar values."""
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def adaptive_router_config(policy: dict[str, Any]) -> dict[str, Any]:
    """Return adaptive router settings merged with conservative defaults."""
    config = dict(router_config.DEFAULT_ADAPTIVE_ROUTER)
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
    config["max_cost_multiplier"] = max(
        1.0, float(config.get("max_cost_multiplier") or 2.0)
    )
    config["critical_risk_threshold"] = clamp01(
        float(config.get("critical_risk_threshold") or 0.65)
    )
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
    failed = (
        success is False
        or int(record.get("returncode") or 0) != 0
        or bool(record.get("error"))
    )
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
    stepped = {state: 0.0 for state in router_config.MARKOV_STATES}
    for source, probability in vector.items():
        for target, transition in router_config.MARKOV_TRANSITIONS[source].items():
            stepped[target] += probability * transition
    if pressure:
        stepped["healthy"] *= 1.0 - 0.55 * pressure
        stepped["warming"] += 0.20 * pressure
        stepped["overloaded"] += 0.45 * pressure
        stepped["failing"] += 0.25 * pressure
        stepped["cooldown"] += 0.10 * pressure
    total = sum(stepped.values()) or 1.0
    return {state: stepped[state] / total for state in router_config.MARKOV_STATES}


def markov_health_for_provider(
    provider: str, records: list[dict[str, Any]], decay: float
) -> dict[str, Any]:
    """Predict the current provider state from recent routing observations."""
    vector = dict(router_config.MARKOV_PRIOR)
    observations = [
        item
        for item in records
        if router_storage.is_business_record(item)
        and (
            item.get("codex_provider") == provider
            or item.get("attempt_provider") == provider
        )
    ]
    for item in observations:
        pressure = provider_observation_pressure(item)
        weighted_pressure = clamp01(pressure * (1.0 - decay) + pressure)
        vector = markov_step(vector, weighted_pressure)
    risk = (
        vector["warming"] * 0.35
        + vector["overloaded"] * 0.75
        + vector["failing"]
        + vector["cooldown"] * 0.45
    )
    state = max(router_config.MARKOV_STATES, key=lambda item: vector[item])
    return {
        "provider": provider,
        "state": state,
        "risk": round(clamp01(risk), 4),
        "score": round(clamp01(1.0 - risk), 4),
        "probabilities": {
            name: round(vector[name], 4) for name in router_config.MARKOV_STATES
        },
        "observations": len(observations),
    }


def weighted_average(parts: list[tuple[float, float]]) -> float | None:
    """Return a weighted average for available performance signals."""
    total_weight = sum(weight for _, weight in parts)
    if total_weight <= 0:
        return None
    return sum(score * weight for score, weight in parts) / total_weight


def provider_observations(
    provider: str, records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return records associated with a provider name."""
    return [
        item
        for item in records
        if router_storage.is_business_record(item)
        and (
            item.get("codex_provider") == provider
            or item.get("attempt_provider") == provider
        )
    ]


def provider_observed_cost(
    provider: str, records: list[dict[str, Any]]
) -> dict[str, Any]:
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
        "average_cost_usd": round(average_cost, 8)
        if average_cost is not None
        else None,
        "cost_observations": len(values),
    }


def provider_observed_performance(
    provider: str, records: list[dict[str, Any]]
) -> dict[str, Any]:
    """Score recent provider utility from latency, TTFT, cost, quality, and failures."""
    observations = provider_observations(provider, records)
    scores: list[float] = []
    for item in observations:
        parts: list[tuple[float, float]] = []
        if item.get("ttft_ms") is not None:
            parts.append((1.0 - metric_pressure(item.get("ttft_ms"), 800, 6_000), 0.24))
        if item.get("latency_ms") is not None:
            parts.append(
                (1.0 - metric_pressure(item.get("latency_ms"), 5_000, 45_000), 0.24)
            )
        if item.get("estimated_cost_usd") is not None:
            parts.append(
                (
                    1.0 - metric_pressure(item.get("estimated_cost_usd"), 0.005, 0.20),
                    0.18,
                )
            )
        if item.get("quality_score") is not None:
            parts.append((clamp01(float(item.get("quality_score") or 0)), 0.18))
        if item.get("error_rate") is not None:
            parts.append((1.0 - clamp01(float(item.get("error_rate") or 0)), 0.16))
        if (
            item.get("success") is not None
            or item.get("returncode") is not None
            or item.get("error")
        ):
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
    records = (history if history is not None else router_storage.read_history())[
        -int(config["max_history"]) :
    ]
    overload_penalty = float(config["overload_penalty"])
    cold_start_penalty = float(config["cold_start_penalty"])
    performance_weight = float(config["performance_weight"])
    min_performance_observations = int(config["min_performance_observations"])
    health = {}
    for provider in fallback_order:
        provider_health = markov_health_for_provider(
            provider, records, float(config["decay"])
        )
        performance = provider_observed_performance(provider, records)
        cost = provider_observed_cost(provider, records)
        cold_start = (
            provider_health["observations"] == 0 and provider != fallback_order[0]
        )
        reliability_score = clamp01(
            float(provider_health["score"])
            - (float(provider_health["risk"]) * overload_penalty)
            - (cold_start_penalty if cold_start else 0.0)
        )
        has_performance = (
            performance["performance_observations"] >= min_performance_observations
        )
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
        key=lambda provider: (
            health[provider]["adjusted_score"],
            -fallback_order.index(provider),
        ),
        reverse=True,
    )
    baseline = fallback_order[0] if fallback_order else "standard"
    suggestion = ranked[0] if ranked else baseline
    confidence_delta = round(
        float(health.get(suggestion, {}).get("adjusted_score", 0))
        - float(health.get(baseline, {}).get("adjusted_score", 0)),
        4,
    )
    would_switch = suggestion != baseline and confidence_delta >= float(
        config["min_confidence_delta"]
    )
    should_switch = (
        bool(config["enabled"]) and not bool(config["shadow_mode"]) and would_switch
    )
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
        cost_guard_blocked = cost_multiplier > float(
            config["max_cost_multiplier"]
        ) and baseline_risk < float(config["critical_risk_threshold"])
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
