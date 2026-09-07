import csv
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_decision_ledger import Decision, DecisionLedger, GovernancePolicy, Outcome
from llm_decision_report import business_evidence, main


class BusinessEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "ledger #1.sqlite3"
        self.ledger = DecisionLedger(self.database)
        self.decision = Decision(
            "req", "review", "model-a", (), "evidence", 0.1,
            selected_provider="provider-a", execution_mode="live",
        )

    def record(self, request_id, *, outcome=True, success=True, score=0.9,
               reviewer="alice", cost=0.1, **changes):
        self.ledger.record_decision(replace(self.decision, request_id=request_id, **changes))
        if outcome:
            self.ledger.record_outcome(Outcome(request_id, success, 10, cost, score, reviewer))

    def test_unit_cost_includes_failures_and_unreviewed_costs(self):
        self.record("accepted", score=0.8)
        self.record("failed", success=False, cost=0.2)
        self.record("automatic", reviewer=" Automatic ", cost=0.3)
        self.record("no-reviewer", reviewer="\t \n", cost=0.4)
        self.record("low-quality", score=0.4, cost=0.5)
        self.record("pending", outcome=False)
        row = business_evidence(self.database)[0]
        self.assertEqual((6, 5, 1, 1, 3, 1), tuple(
            row[k] for k in ("decisions", "completed", "pending", "failed", "reviewed", "accepted")
        ))
        self.assertAlmostEqual(1.5, row["cost_per_accepted_usd"])
        self.assertAlmostEqual(0.6, row["review_coverage"])
        self.assertAlmostEqual(1 / 3, row["acceptance_rate"])
        self.assertTrue(row["cost_is_partial"])

    def test_contexts_are_separate_and_live_is_default(self):
        self.record("a")
        self.record("b", selected_provider="provider-b")
        self.record("c", task_type="translation")
        self.record("d", execution_mode="shadow")
        self.assertEqual(3, len(business_evidence(self.database)))
        self.assertEqual(4, len(business_evidence(self.database, execution_mode="all")))
        self.assertEqual(1, len(business_evidence(self.database, execution_mode="shadow")))
        self.assertEqual(2, len(business_evidence(self.database, task_type="review")))
        self.assertEqual([], business_evidence(self.database, task_type="' OR 1=1 --"))

    def test_missing_acceptance_is_unknown_not_free(self):
        self.record("a", score=None)
        row = business_evidence(self.database)[0]
        self.assertIsNone(row["cost_per_accepted_usd"])
        self.assertIsNone(row["acceptance_rate"])
        self.assertEqual(0, row["review_coverage"])
        self.assertFalse(row["cost_is_partial"])

    def test_pending_only_and_empty_ledger(self):
        self.assertEqual([], business_evidence(self.database))
        self.record("pending", outcome=False)
        row = business_evidence(self.database)[0]
        self.assertIsNone(row["review_coverage"])
        self.assertIsNone(row["cost_per_accepted_usd"])
        self.assertTrue(row["cost_is_partial"])

    def test_report_is_read_only_and_missing_path_is_not_created(self):
        self.record("a")
        before = self.database.read_bytes()
        business_evidence(self.database)
        self.assertEqual(before, self.database.read_bytes())
        missing = self.database.with_name("missing.sqlite3")
        with self.assertRaises(sqlite3.OperationalError):
            business_evidence(missing)
        self.assertFalse(missing.exists())

    def test_filters_are_validated(self):
        for value in (-0.1, 1.1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                business_evidence(self.database, quality_threshold=value)
        with self.assertRaises(ValueError):
            business_evidence(self.database, execution_mode="invalid")

    def test_cli_json_csv_and_failure(self):
        self.record("a")
        for format_name in ("json", "csv"):
            out = io.StringIO()
            with redirect_stdout(out):
                code = main([str(self.database), "--format", format_name])
            self.assertEqual(0, code)
            if format_name == "json":
                payload = json.loads(out.getvalue())
                self.assertEqual(0.8, payload["quality_threshold"])
                self.assertEqual(1, payload["groups"][0]["accepted"])
            else:
                self.assertEqual("1", list(csv.DictReader(io.StringIO(out.getvalue())))[0]["accepted"])
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([str(self.database), "--quality-threshold", "nan"])
        self.assertEqual(1, code)
        self.assertEqual("", out.getvalue())
        self.assertIn("finite", err.getvalue())

    def test_integer_cost_integrity_round_trip(self):
        for cost in (0, 1):
            decision = replace(self.decision, request_id=str(cost), estimated_cost_usd=cost)
            digest = self.ledger.record_decision(decision)
            self.assertEqual(digest, self.ledger.integrity_hash(decision))
            self.assertTrue(self.ledger.verify(str(cost)))

    def test_rejects_nonfinite_costs_and_policy(self):
        for value in (float("nan"), float("inf"), -float("inf"), -1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.ledger.record_decision(replace(self.decision, estimated_cost_usd=value))
                with self.assertRaises(ValueError):
                    GovernancePolicy(max_live_estimated_cost_usd=value)
        self.record("a", outcome=False)
        for change in ({"actual_cost_usd": float("inf")}, {"actual_cost_usd": float("nan")},
                       {"success": "false"}, {"latency_ms": float("inf")}, {"latency_ms": 1.5}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.ledger.record_outcome(replace(Outcome("a", True, 1, 0.1), **change))


if __name__ == "__main__":
    unittest.main()
