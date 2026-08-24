"""Guardrail-aware meta-optimizer for provider-neutral LLM routing."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional

from llm_decision_ledger import (
    DATA_BOUNDARIES,
    DATA_CLASSIFICATIONS,
    EXECUTION_MODES,
    RISK_LEVELS,
    Decision,
    DecisionLedger,
    GovernancePolicy,
    GuardrailViolation,
)


class NoEligibleCandidate(RuntimeError):
    """Raised when mandatory constraints reject every model candidate."""


@dataclass(frozen=True)
class ModelCandidate:
    """Observed model performance for one task and customer context."""

    model: str
    provider: str
    data_boundary: str
    estimated_cost_usd: float
    latency_ms_p95: int
    quality_score: float
    success_rate: float
    sample_count: int
    capabilities: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.model.strip() or not self.provider.strip():
            raise ValueError("candidate model and provider cannot be empty")
        if self.data_boundary not in DATA_BOUNDARIES:
            raise ValueError(f"unsupported data_boundary: {self.data_boundary}")
        if self.estimated_cost_usd < 0 or self.latency_ms_p95 < 0:
            raise ValueError("candidate cost and latency must be non-negative")
        if not 0 <= self.quality_score <= 1 or not 0 <= self.success_rate <= 1:
            raise ValueError(
                "candidate quality and success rate must be between 0 and 1"
            )
        if self.sample_count < 0:
            raise ValueError("candidate sample_count must be non-negative")

    @property
    def identifier(self) -> str:
        return f"{self.provider}/{self.model}"


@dataclass(frozen=True)
class RoutingRequest:
    """Constraints and governance context for a meta-routing decision."""

    request_id: str
    task_type: str
    risk_level: str = "medium"
    data_classification: str = "internal"
    execution_mode: str = "shadow"
    policy_version: str = "draft"
    approved_by: Optional[str] = None
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    allowed_providers: tuple[str, ...] = ()
    max_cost_usd: Optional[float] = None
    max_latency_ms_p95: Optional[int] = None
    min_quality_score: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.task_type.strip():
            raise ValueError("request_id and task_type cannot be empty")
        if not self.policy_version.strip():
            raise ValueError("policy_version cannot be empty")
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(f"unsupported risk_level: {self.risk_level}")
        if self.data_classification not in DATA_CLASSIFICATIONS:
            raise ValueError(
                f"unsupported data_classification: {self.data_classification}"
            )
        if self.execution_mode not in EXECUTION_MODES:
            raise ValueError(f"unsupported execution_mode: {self.execution_mode}")
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be non-negative")
        if self.max_latency_ms_p95 is not None and self.max_latency_ms_p95 < 0:
            raise ValueError("max_latency_ms_p95 must be non-negative")
        if self.min_quality_score is not None and not 0 <= self.min_quality_score <= 1:
            raise ValueError("min_quality_score must be between 0 and 1")


@dataclass(frozen=True)
class OptimizationProfile:
    """Weights selected by the meta-layer for the second-stage ranking."""

    name: str
    quality: float
    reliability: float
    latency: float
    cost: float

    def __post_init__(self) -> None:
        weights = (self.quality, self.reliability, self.latency, self.cost)
        if any(weight < 0 for weight in weights) or sum(weights) <= 0:
            raise ValueError("profile weights must be non-negative with a positive sum")

    @property
    def normalized_weights(self) -> tuple[float, float, float, float]:
        total = self.quality + self.reliability + self.latency + self.cost
        return (
            self.quality / total,
            self.reliability / total,
            self.latency / total,
            self.cost / total,
        )


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: ModelCandidate
    score: float


@dataclass(frozen=True)
class CandidateRejection:
    candidate_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class MetaDecision:
    selected: ModelCandidate
    profile_name: str
    ranked_candidates: tuple[ScoredCandidate, ...]
    rejected_candidates: tuple[CandidateRejection, ...]
    shadow_candidate: Optional[ModelCandidate]
    explanation: str


DEFAULT_PROFILES = (
    OptimizationProfile("balanced", 0.35, 0.25, 0.20, 0.20),
    OptimizationProfile("quality", 0.65, 0.30, 0.04, 0.01),
    OptimizationProfile("cost", 0.25, 0.20, 0.10, 0.45),
    OptimizationProfile("latency", 0.25, 0.20, 0.45, 0.10),
)


class MetaOptimizer:
    """Select an objective, rank eligible candidates, and record the decision."""

    def __init__(
        self,
        profiles: Iterable[OptimizationProfile] = DEFAULT_PROFILES,
        prior_samples: int = 5,
    ) -> None:
        if prior_samples < 0:
            raise ValueError("prior_samples must be non-negative")
        self.profiles = {profile.name: profile for profile in profiles}
        required_profiles = {"balanced", "quality", "cost", "latency"}
        if set(self.profiles) != required_profiles:
            raise ValueError(f"profiles must be exactly: {sorted(required_profiles)}")
        self.prior_samples = prior_samples

    def optimize(
        self,
        request: RoutingRequest,
        candidates: Iterable[ModelCandidate],
        policy: Optional[GovernancePolicy] = None,
    ) -> MetaDecision:
        """Return a deterministic, explainable choice after fail-closed filtering."""
        active_policy = policy or GovernancePolicy()
        self._validate_live_request(request, active_policy)
        candidate_list = tuple(candidates)
        if not candidate_list:
            raise NoEligibleCandidate("no model candidates were supplied")
        identifiers = [candidate.identifier for candidate in candidate_list]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("candidate provider/model identifiers must be unique")

        eligible: list[ModelCandidate] = []
        rejected: list[CandidateRejection] = []
        for candidate in candidate_list:
            reasons = self._rejection_reasons(request, candidate, active_policy)
            if reasons:
                rejected.append(
                    CandidateRejection(candidate.identifier, tuple(reasons))
                )
            else:
                eligible.append(candidate)
        if not eligible:
            detail = "; ".join(
                f"{item.candidate_id}: {', '.join(item.reasons)}" for item in rejected
            )
            raise NoEligibleCandidate(f"all candidates rejected ({detail})")

        profile = self._select_profile(request, tuple(eligible), active_policy)
        ranked = self._rank(profile, eligible)
        selected = ranked[0].candidate
        shadow = self._select_shadow_candidate(selected, eligible)
        explanation = (
            f"meta-profile={profile.name}; score={ranked[0].score:.4f}; "
            f"eligible={len(eligible)}; rejected={len(rejected)}"
        )
        return MetaDecision(
            selected=selected,
            profile_name=profile.name,
            ranked_candidates=ranked,
            rejected_candidates=tuple(rejected),
            shadow_candidate=shadow,
            explanation=explanation,
        )

    def optimize_and_record(
        self,
        request: RoutingRequest,
        candidates: Iterable[ModelCandidate],
        ledger: DecisionLedger,
    ) -> tuple[MetaDecision, str]:
        """Optimize with the ledger policy, then persist its integrity proof."""
        result = self.optimize(request, candidates, policy=ledger.policy)
        alternatives = tuple(
            item.candidate.model for item in result.ranked_candidates[1:]
        )
        decision = Decision(
            request_id=request.request_id,
            task_type=request.task_type,
            selected_model=result.selected.model,
            selected_provider=result.selected.provider,
            alternative_models=alternatives,
            reason=result.explanation,
            estimated_cost_usd=result.selected.estimated_cost_usd,
            risk_level=request.risk_level,
            data_classification=request.data_classification,
            data_boundary=result.selected.data_boundary,
            execution_mode=request.execution_mode,
            policy_version=request.policy_version,
            approved_by=request.approved_by,
        )
        return result, ledger.record_decision(decision)

    @staticmethod
    def _validate_live_request(
        request: RoutingRequest, policy: GovernancePolicy
    ) -> None:
        if request.execution_mode != "live":
            return
        if (
            request.risk_level in policy.approval_risk_levels
            and not (request.approved_by or "").strip()
        ):
            raise GuardrailViolation(
                f"live {request.risk_level}-risk decisions require human approval"
            )

    @staticmethod
    def _rejection_reasons(
        request: RoutingRequest,
        candidate: ModelCandidate,
        policy: GovernancePolicy,
    ) -> list[str]:
        reasons: list[str] = []
        if (
            request.allowed_providers
            and candidate.provider not in request.allowed_providers
        ):
            reasons.append("provider is not allowed")
        missing = request.required_capabilities - candidate.capabilities
        if missing:
            reasons.append(f"missing capabilities: {', '.join(sorted(missing))}")
        if (
            request.execution_mode == "live"
            and request.data_classification in policy.local_only_data_classifications
            and candidate.data_boundary != "local"
        ):
            reasons.append("data boundary must be local")
        cost_ceiling = request.max_cost_usd
        if (
            request.execution_mode == "live"
            and policy.max_live_estimated_cost_usd is not None
        ):
            cost_ceiling = (
                policy.max_live_estimated_cost_usd
                if cost_ceiling is None
                else min(cost_ceiling, policy.max_live_estimated_cost_usd)
            )
        if cost_ceiling is not None and candidate.estimated_cost_usd > cost_ceiling:
            reasons.append("estimated cost exceeds ceiling")
        if (
            request.max_latency_ms_p95 is not None
            and candidate.latency_ms_p95 > request.max_latency_ms_p95
        ):
            reasons.append("p95 latency exceeds ceiling")
        if (
            request.min_quality_score is not None
            and candidate.quality_score < request.min_quality_score
        ):
            reasons.append("quality is below floor")
        return reasons

    def _select_profile(
        self,
        request: RoutingRequest,
        candidates: tuple[ModelCandidate, ...],
        policy: GovernancePolicy,
    ) -> OptimizationProfile:
        if request.risk_level in {"high", "critical"}:
            return self.profiles["quality"]

        pressures: dict[str, float] = {}
        cost_ceiling = request.max_cost_usd
        if (
            request.execution_mode == "live"
            and policy.max_live_estimated_cost_usd is not None
        ):
            cost_ceiling = (
                policy.max_live_estimated_cost_usd
                if cost_ceiling is None
                else min(cost_ceiling, policy.max_live_estimated_cost_usd)
            )
        if cost_ceiling is not None:
            pressures["cost"] = self._average_ratio(
                (candidate.estimated_cost_usd for candidate in candidates), cost_ceiling
            )
        if request.max_latency_ms_p95 is not None:
            pressures["latency"] = self._average_ratio(
                (float(candidate.latency_ms_p95) for candidate in candidates),
                float(request.max_latency_ms_p95),
            )
        if request.min_quality_score is not None:
            average_quality = sum(c.quality_score for c in candidates) / len(candidates)
            pressures["quality"] = request.min_quality_score / max(
                average_quality, 1e-12
            )
        if not pressures:
            return self.profiles["balanced"]
        selected_name = max(
            ("quality", "cost", "latency"),
            key=lambda name: pressures.get(name, -1.0),
        )
        return self.profiles[selected_name]

    @staticmethod
    def _average_ratio(values: Iterable[float], ceiling: float) -> float:
        value_list = tuple(values)
        if ceiling == 0:
            return math.inf if any(value > 0 for value in value_list) else 0.0
        return sum(value / ceiling for value in value_list) / len(value_list)

    def _rank(
        self,
        profile: OptimizationProfile,
        candidates: list[ModelCandidate],
    ) -> tuple[ScoredCandidate, ...]:
        quality = [
            self._confidence_adjusted(c.quality_score, c.sample_count)
            for c in candidates
        ]
        reliability = [
            self._confidence_adjusted(c.success_rate, c.sample_count)
            for c in candidates
        ]
        latency = self._lower_is_better(
            [float(c.latency_ms_p95) for c in candidates]
        )
        cost = self._lower_is_better([c.estimated_cost_usd for c in candidates])
        weights = profile.normalized_weights
        scored = [
            ScoredCandidate(
                candidate=candidate,
                score=(
                    weights[0] * quality[index]
                    + weights[1] * reliability[index]
                    + weights[2] * latency[index]
                    + weights[3] * cost[index]
                ),
            )
            for index, candidate in enumerate(candidates)
        ]
        return tuple(
            sorted(
                scored,
                key=lambda item: (-item.score, item.candidate.identifier),
            )
        )

    def _confidence_adjusted(self, value: float, samples: int) -> float:
        if self.prior_samples == 0:
            return value
        return (samples * value + self.prior_samples * 0.5) / (
            samples + self.prior_samples
        )

    @staticmethod
    def _lower_is_better(values: list[float]) -> list[float]:
        lowest = min(values)
        highest = max(values)
        if highest == lowest:
            return [1.0] * len(values)
        return [1.0 - ((value - lowest) / (highest - lowest)) for value in values]

    @staticmethod
    def _select_shadow_candidate(
        selected: ModelCandidate,
        candidates: list[ModelCandidate],
    ) -> Optional[ModelCandidate]:
        alternatives = [candidate for candidate in candidates if candidate != selected]
        if not alternatives:
            return None
        return min(
            alternatives,
            key=lambda candidate: (candidate.sample_count, candidate.identifier),
        )
