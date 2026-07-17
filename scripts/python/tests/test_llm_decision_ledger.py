import sys
import tempfile
import unittest
from pathlib import Path

# unittest discovery starts from the repository root, so expose the sibling module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_decision_ledger import Decision, DecisionLedger, Outcome


class DecisionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ledger = DecisionLedger(Path(self.temp_dir.name) / "ledger.sqlite3")
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


if __name__ == "__main__":
    unittest.main()
