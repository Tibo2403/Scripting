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


@dataclass(frozen=True)
class Decision:
    request_id: str
    task_type: str
    selected_model: str
    alternative_models: tuple[str, ...]
    reason: str
    estimated_cost_usd: float
    risk_level: str = "medium"


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

    def __init__(self, database: str | Path = "llm_decisions.sqlite3") -> None:
        self.database = str(database)
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

    @staticmethod
    def _canonical_payload(decision: Decision) -> str:
        payload = asdict(decision)
        payload["alternative_models"] = list(decision.alternative_models)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @classmethod
    def integrity_hash(cls, decision: Decision) -> str:
        return hashlib.sha256(cls._canonical_payload(decision).encode("utf-8")).hexdigest()

    def record_decision(self, decision: Decision) -> str:
        if not decision.request_id.strip():
            raise ValueError("request_id cannot be empty")
        if decision.estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd cannot be negative")

        digest = self.integrity_hash(decision)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        )
        return self.integrity_hash(decision) == row["integrity_hash"]
