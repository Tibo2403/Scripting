import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

# unittest discovery starts from the repository root, so expose the sibling module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_decision_ledger import (
    Decision,
    DecisionLedger,
    GovernancePolicy,
    GuardrailViolation,
    Outcome,
)


class DecisionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "ledger.sqlite3"
        self.ledger = DecisionLedger(self.database)
        self.decision = Decision(
            request_id="req-001",
            task_type="code-review",
            selected_model="model-a",
            alternative_models=("model-b",),
            reason="Best historical quality under the cost ceiling",
            estimated_cost_usd=0.02,
            risk_level="high",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_records_and_verifies_decision(self):
        digest = self.ledger.record_decision(self.decision)
        self.assertEqual(64, len(digest))
        self.assertTrue(self.ledger.verify("req-001"))

    def test_releases_database_file_after_operation(self):
        self.ledger.record_decision(self.decision)
        self.database.unlink()
        self.assertFalse(self.database.exists())

    def test_records_outcome_and_builds_evidence(self):
        self.ledger.record_decision(self.decision)
        self.ledger.record_outcome(
            Outcome(
                request_id="req-001",
                success=True,
                latency_ms=800,
                actual_cost_usd=0.018,
                quality_score=0.9,
            )
        )
        evidence = self.ledger.model_evidence("code-review")
        self.assertEqual(1, len(evidence))
        self.assertEqual("model-a", evidence[0]["model"])
        self.assertAlmostEqual(0.9, evidence[0]["average_quality_score"])

    def test_rejects_outcome_without_decision(self):
        with self.assertRaises(KeyError):
            self.ledger.record_outcome(
                Outcome("missing", True, 10, 0.0, quality_score=1.0)
            )

    def test_rejects_invalid_quality_score(self):
        self.ledger.record_decision(self.decision)
        with self.assertRaises(ValueError):
            self.ledger.record_outcome(
                Outcome("req-001", True, 10, 0.0, quality_score=1.5)
            )

    def test_live_high_risk_decision_requires_human_approval(self):
        decision = Decision(
            **{
                **self.decision.__dict__,
                "execution_mode": "live",
                "policy_version": "security-v1",
            }
        )
        with self.assertRaises(GuardrailViolation):
            self.ledger.record_decision(decision)

    def test_approved_live_high_risk_decision_is_recorded(self):
        decision = Decision(
            **{
                **self.decision.__dict__,
                "execution_mode": "live",
                "policy_version": "security-v1",
                "approved_by": "reviewer@example.invalid",
            }
        )
        self.ledger.record_decision(decision)
        self.assertTrue(self.ledger.verify(decision.request_id))

    def test_restricted_data_cannot_leave_local_boundary(self):
        decision = Decision(
            **{
                **self.decision.__dict__,
                "execution_mode": "live",
                "data_classification": "restricted",
                "data_boundary": "external",
                "policy_version": "residency-v1",
                "approved_by": "reviewer@example.invalid",
            }
        )
        with self.assertRaises(GuardrailViolation):
            self.ledger.record_decision(decision)

    def test_live_cost_ceiling_is_fail_closed(self):
        ledger = DecisionLedger(
            self.database,
            policy=GovernancePolicy(max_live_estimated_cost_usd=0.01),
        )
        decision = Decision(
            **{
                **self.decision.__dict__,
                "execution_mode": "live",
                "risk_level": "low",
                "policy_version": "cost-v1",
            }
        )
        with self.assertRaises(GuardrailViolation):
            ledger.record_decision(decision)

    def test_migrates_and_verifies_legacy_decision(self):
        legacy_database = Path(self.temp_dir.name) / "legacy.sqlite3"
        payload = {
            "request_id": "legacy-001",
            "task_type": "code-review",
            "selected_model": "model-a",
            "alternative_models": ["model-b"],
            "reason": "Legacy routing evidence",
            "estimated_cost_usd": 0.01,
            "risk_level": "medium",
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        with closing(sqlite3.connect(legacy_database)) as connection:
            connection.execute(
                """
                CREATE TABLE decisions (
                    request_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    selected_model TEXT NOT NULL,
                    alternative_models TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    integrity_hash TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    payload["request_id"],
                    "2026-01-01T00:00:00+00:00",
                    payload["task_type"],
                    payload["selected_model"],
                    json.dumps(payload["alternative_models"]),
                    payload["reason"],
                    payload["estimated_cost_usd"],
                    payload["risk_level"],
                    digest,
                ),
            )
            connection.execute(
                """
                CREATE TABLE outcomes (
                    request_id TEXT PRIMARY KEY REFERENCES decisions(request_id),
                    created_at TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    actual_cost_usd REAL NOT NULL,
                    quality_score REAL,
                    reviewer TEXT NOT NULL,
                    notes TEXT NOT NULL
                )
                """
            )
            connection.commit()

        migrated = DecisionLedger(legacy_database)
        self.assertTrue(migrated.verify("legacy-001"))

        migrated.record_decision(
            Decision(
                request_id="new-001",
                task_type="classification",
                selected_model="local-model",
                selected_provider="local",
                alternative_models=[],
                reason="Low-risk request after migration",
                estimated_cost_usd=0.0,
                risk_level="low",
                execution_mode="live",
                policy_version="policy-v2",
            )
        )
        self.assertTrue(migrated.verify("new-001"))


if __name__ == "__main__":
    unittest.main()
