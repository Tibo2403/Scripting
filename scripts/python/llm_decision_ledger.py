"""Provider-neutral decision ledger for LLM engineering workflows.

This module does not proxy model traffic. It records routing intent, outcomes,
and evidence so an existing gateway such as LiteLLM, OpenRouter, a direct SDK,
or an internal platform can make auditable and continuously improving choices.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


RISK_LEVELS = frozenset({"low", "medium", "high", "critical"})
DATA_CLASSIFICATIONS = frozenset({"public", "internal", "confidential", "restricted"})
DATA_BOUNDARIES = frozenset({"local", "approved-region", "external"})
EXECUTION_MODES = frozenset({"shadow", "live"})


class GuardrailViolation(ValueError):
    """Raised when a routing decision violates a mandatory governance rule."""


@dataclass(frozen=True)
class GovernancePolicy:
    """Fail-closed controls applied before a live decision is recorded."""

    approval_risk_levels: tuple[str, ...] = ("high", "critical")
    local_only_data_classifications: tuple[str, ...] = ("restricted",)
    max_live_estimated_cost_usd: Optional[float] = None


@dataclass(frozen=True)
class Decision:
    request_id: str
    task_type: str
    selected_model: str
    alternative_models: tuple[str, ...]
    reason: str
    estimated_cost_usd: float
    risk_level: str = "medium"
    selected_provider: str = "unspecified"
    data_classification: str = "internal"
    data_boundary: str = "external"
    execution_mode: str = "shadow"
    policy_version: str = "draft"
    approved_by: Optional[str] = None


@dataclass(frozen=True)
class Outcome:
    request_id: str
    success: bool
    latency_ms: int
    actual_cost_usd: float
    quality_score: Optional[float] = None
    reviewer: str = "automatic"
    notes: str = ""


class DecisionLedger:
    """Append-only SQLite ledger with simple model evidence summaries."""

    def __init__(
        self,
        database: str | Path = "llm_decisions.sqlite3",
        policy: Optional[GovernancePolicy] = None,
    ) -> None:
        self.database = str(database)
        self.policy = policy or GovernancePolicy()
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    request_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    selected_model TEXT NOT NULL,
                    alternative_models TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    estimated_cost_usd REAL NOT NULL CHECK(estimated_cost_usd >= 0),
                    risk_level TEXT NOT NULL,
                    selected_provider TEXT NOT NULL,
                    data_classification TEXT NOT NULL,
                    data_boundary TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    approved_by TEXT,
                    integrity_version INTEGER NOT NULL DEFAULT 2,
                    integrity_hash TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS outcomes (
                    request_id TEXT PRIMARY KEY REFERENCES decisions(request_id),
                    created_at TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL CHECK(latency_ms >= 0),
                    actual_cost_usd REAL NOT NULL CHECK(actual_cost_usd >= 0),
                    quality_score REAL,
                    reviewer TEXT NOT NULL,
                    notes TEXT NOT NULL
                );
                """
            )
            self._migrate_decision_columns(connection)

    @staticmethod
    def _migrate_decision_columns(connection: sqlite3.Connection) -> None:
        """Add governance fields without invalidating version-one ledger rows."""
        existing = {
            row["name"] for row in connection.execute("PRAGMA table_info(decisions)")
        }
        governance_existed = "policy_version" in existing
        additions = {
            "selected_provider": "TEXT NOT NULL DEFAULT 'unspecified'",
            "data_classification": "TEXT NOT NULL DEFAULT 'internal'",
            "data_boundary": "TEXT NOT NULL DEFAULT 'external'",
            "execution_mode": "TEXT NOT NULL DEFAULT 'shadow'",
            "policy_version": "TEXT NOT NULL DEFAULT 'legacy-v1'",
            "approved_by": "TEXT",
        }
        for column, definition in additions.items():
            if column not in existing:
                connection.execute(
                    f"ALTER TABLE decisions ADD COLUMN {column} {definition}"
                )
        if "integrity_version" not in existing:
            default_version = 2 if governance_existed else 1
            connection.execute(
                "ALTER TABLE decisions ADD COLUMN integrity_version "
                f"INTEGER NOT NULL DEFAULT {default_version}"
            )

    @staticmethod
    def _canonical_payload(decision: Decision) -> str:
        payload = asdict(decision)
        payload["alternative_models"] = list(decision.alternative_models)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _legacy_canonical_payload(decision: Decision) -> str:
        payload = {
            "request_id": decision.request_id,
            "task_type": decision.task_type,
            "selected_model": decision.selected_model,
            "alternative_models": list(decision.alternative_models),
            "reason": decision.reason,
            "estimated_cost_usd": decision.estimated_cost_usd,
            "risk_level": decision.risk_level,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @classmethod
    def integrity_hash(cls, decision: Decision) -> str:
        return hashlib.sha256(cls._canonical_payload(decision).encode("utf-8")).hexdigest()

    def _validate_decision(self, decision: Decision) -> None:
        required_text = {
            "request_id": decision.request_id,
            "task_type": decision.task_type,
            "selected_model": decision.selected_model,
            "reason": decision.reason,
            "selected_provider": decision.selected_provider,
            "policy_version": decision.policy_version,
        }
        empty_fields = [name for name, value in required_text.items() if not value.strip()]
        if empty_fields:
            raise ValueError(f"required fields cannot be empty: {', '.join(empty_fields)}")
        if decision.estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd cannot be negative")
        if decision.risk_level not in RISK_LEVELS:
            raise ValueError(f"unsupported risk_level: {decision.risk_level}")
        if decision.data_classification not in DATA_CLASSIFICATIONS:
            raise ValueError(
                f"unsupported data_classification: {decision.data_classification}"
            )
        if decision.data_boundary not in DATA_BOUNDARIES:
            raise ValueError(f"unsupported data_boundary: {decision.data_boundary}")
        if decision.execution_mode not in EXECUTION_MODES:
            raise ValueError(f"unsupported execution_mode: {decision.execution_mode}")

        # Shadow decisions never dispatch traffic, so they may be recorded for
        # comparison even when they would not yet be allowed in production.
        if decision.execution_mode == "shadow":
            return

        if (
            decision.risk_level in self.policy.approval_risk_levels
            and not (decision.approved_by or "").strip()
        ):
            raise GuardrailViolation(
                f"live {decision.risk_level}-risk decisions require human approval"
            )
        if (
            decision.data_classification
            in self.policy.local_only_data_classifications
            and decision.data_boundary != "local"
        ):
            raise GuardrailViolation(
                f"live {decision.data_classification} data must remain local"
            )
        cost_ceiling = self.policy.max_live_estimated_cost_usd
        if cost_ceiling is not None and decision.estimated_cost_usd > cost_ceiling:
            raise GuardrailViolation(
                "estimated live cost exceeds the configured decision ceiling"
            )

    def record_decision(self, decision: Decision) -> str:
        self._validate_decision(decision)

        digest = self.integrity_hash(decision)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO decisions (
                    request_id,
                    created_at,
                    task_type,
                    selected_model,
                    alternative_models,
                    reason,
                    estimated_cost_usd,
                    risk_level,
                    selected_provider,
                    data_classification,
                    data_boundary,
                    execution_mode,
                    policy_version,
                    approved_by,
                    integrity_version,
                    integrity_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.request_id,
                    datetime.now(timezone.utc).isoformat(),
                    decision.task_type,
                    decision.selected_model,
                    json.dumps(decision.alternative_models),
                    decision.reason,
                    decision.estimated_cost_usd,
                    decision.risk_level,
                    decision.selected_provider,
                    decision.data_classification,
                    decision.data_boundary,
                    decision.execution_mode,
                    decision.policy_version,
                    decision.approved_by,
                    2,
                    digest,
                ),
            )
        return digest

    def record_outcome(self, outcome: Outcome) -> None:
        if outcome.latency_ms < 0 or outcome.actual_cost_usd < 0:
            raise ValueError("latency and cost must be non-negative")
        if outcome.quality_score is not None and not 0 <= outcome.quality_score <= 1:
            raise ValueError("quality_score must be between 0 and 1")

        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM decisions WHERE request_id = ?", (outcome.request_id,)
            ).fetchone()
            if not exists:
                raise KeyError(f"unknown request_id: {outcome.request_id}")
            connection.execute(
                """
                INSERT INTO outcomes VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome.request_id,
                    datetime.now(timezone.utc).isoformat(),
                    int(outcome.success),
                    outcome.latency_ms,
                    outcome.actual_cost_usd,
                    outcome.quality_score,
                    outcome.reviewer,
                    outcome.notes,
                ),
            )

    def model_evidence(self, task_type: Optional[str] = None) -> list[dict[str, object]]:
        filters = "WHERE d.task_type = ?" if task_type else ""
        params: Iterable[object] = (task_type,) if task_type else ()
        query = f"""
            SELECT
                d.selected_model AS model,
                COUNT(*) AS samples,
                AVG(o.success) AS success_rate,
                AVG(o.latency_ms) AS average_latency_ms,
                AVG(o.actual_cost_usd) AS average_cost_usd,
                AVG(o.quality_score) AS average_quality_score
            FROM decisions d
            JOIN outcomes o ON o.request_id = d.request_id
            {filters}
            GROUP BY d.selected_model
            ORDER BY average_quality_score DESC, success_rate DESC, average_cost_usd ASC
        """
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, tuple(params)).fetchall()]

    def verify(self, request_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM decisions WHERE request_id = ?", (request_id,)
            ).fetchone()
        if row is None:
            return False
        decision = Decision(
            request_id=row["request_id"],
            task_type=row["task_type"],
            selected_model=row["selected_model"],
            alternative_models=tuple(json.loads(row["alternative_models"])),
            reason=row["reason"],
            estimated_cost_usd=row["estimated_cost_usd"],
            risk_level=row["risk_level"],
            selected_provider=row["selected_provider"],
            data_classification=row["data_classification"],
            data_boundary=row["data_boundary"],
            execution_mode=row["execution_mode"],
            policy_version=row["policy_version"],
            approved_by=row["approved_by"],
        )
        if row["integrity_version"] == 1:
            expected = hashlib.sha256(
                self._legacy_canonical_payload(decision).encode("utf-8")
            ).hexdigest()
        else:
            expected = self.integrity_hash(decision)
        return expected == row["integrity_hash"]
