import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_decision_ledger import DecisionLedger, GovernancePolicy, GuardrailViolation
from llm_meta_optimizer import (
    MetaOptimizer,
    ModelCandidate,
    NoEligibleCandidate,
    RoutingRequest,
)


class MetaOptimizerTests(unittest.TestCase):
    def setUp(self):
        self.optimizer = MetaOptimizer()
        self.fast_cheap = ModelCandidate(
            model="small",
            provider="provider-a",
            data_boundary="external",
            estimated_cost_usd=0.01,
            latency_ms_p95=400,
            quality_score=0.72,
            success_rate=0.92,
            sample_count=100,
            capabilities=frozenset({"json"}),
        )
        self.high_quality = ModelCandidate(
            model="large",
            provider="provider-b",
            data_boundary="approved-region",
            estimated_cost_usd=0.08,
            latency_ms_p95=1800,
            quality_score=0.97,
            success_rate=0.98,
            sample_count=80,
            capabilities=frozenset({"json", "tools"}),
        )

    def test_high_risk_request_selects_quality_profile(self):
        result = self.optimizer.optimize(
            RoutingRequest(
                request_id="req-high",
                task_type="code-review",
                risk_level="high",
                execution_mode="live",
                policy_version="risk-v1",
                approved_by="reviewer@example.invalid",
            ),
            (self.fast_cheap, self.high_quality),
        )
        self.assertEqual("quality", result.profile_name)
        self.assertEqual("large", result.selected.model)

    def test_cost_pressure_filters_and_selects_cheap_candidate(self):
        result = self.optimizer.optimize(
            RoutingRequest(
                request_id="req-cost",
                task_type="classification",
                max_cost_usd=0.02,
            ),
            (self.fast_cheap, self.high_quality),
        )
        self.assertEqual("cost", result.profile_name)
        self.assertEqual("small", result.selected.model)
        self.assertEqual("provider-b/large", result.rejected_candidates[0].candidate_id)

    def test_restricted_live_data_rejects_non_local_candidates(self):
        request = RoutingRequest(
            request_id="req-private",
            task_type="summarization",
            data_classification="restricted",
            execution_mode="live",
            policy_version="residency-v1",
        )
        with self.assertRaises(NoEligibleCandidate):
            self.optimizer.optimize(request, (self.fast_cheap, self.high_quality))

    def test_live_high_risk_request_fails_without_approval(self):
        request = RoutingRequest(
            request_id="req-blocked",
            task_type="code-review",
            risk_level="critical",
            execution_mode="live",
            policy_version="risk-v1",
        )
        with self.assertRaises(GuardrailViolation):
            self.optimizer.optimize(request, (self.high_quality,))

    def test_required_capability_is_fail_closed(self):
        request = RoutingRequest(
            request_id="req-vision",
            task_type="image-analysis",
            required_capabilities=frozenset({"vision"}),
        )
        with self.assertRaises(NoEligibleCandidate):
            self.optimizer.optimize(request, (self.fast_cheap, self.high_quality))

    def test_rejected_candidate_cannot_influence_profile_selection(self):
        disallowed = ModelCandidate(
            model="manipulative",
            provider="provider-blocked",
            data_boundary="external",
            estimated_cost_usd=100.0,
            latency_ms_p95=10,
            quality_score=1.0,
            success_rate=1.0,
            sample_count=100,
        )
        result = self.optimizer.optimize(
            RoutingRequest(
                request_id="req-isolated",
                task_type="classification",
                allowed_providers=frozenset({"provider-a", "provider-b"}),
                max_cost_usd=1.0,
                max_latency_ms_p95=2_000,
            ),
            (self.fast_cheap, self.high_quality, disallowed),
        )
        self.assertEqual("latency", result.profile_name)
        self.assertEqual(
            "provider-blocked/manipulative",
            result.rejected_candidates[0].candidate_id,
        )

    def test_optimization_is_recorded_with_ledger_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "ledger.sqlite3"
            ledger = DecisionLedger(
                database,
                policy=GovernancePolicy(max_live_estimated_cost_usd=0.02),
            )
            result, digest = self.optimizer.optimize_and_record(
                RoutingRequest(
                    request_id="req-recorded",
                    task_type="classification",
                    risk_level="low",
                    execution_mode="live",
                    policy_version="meta-v1",
                ),
                (self.fast_cheap, self.high_quality),
                ledger,
            )
            self.assertEqual("small", result.selected.model)
            self.assertEqual(64, len(digest))
            self.assertTrue(ledger.verify("req-recorded"))

    def test_low_evidence_alternative_is_selected_for_shadow_learning(self):
        emerging = ModelCandidate(
            model="emerging",
            provider="provider-c",
            data_boundary="external",
            estimated_cost_usd=0.02,
            latency_ms_p95=900,
            quality_score=0.8,
            success_rate=0.8,
            sample_count=2,
        )
        result = self.optimizer.optimize(
            RoutingRequest(request_id="req-shadow", task_type="classification"),
            (self.fast_cheap, self.high_quality, emerging),
        )
        self.assertIsNotNone(result.shadow_candidate)
        self.assertEqual("emerging", result.shadow_candidate.model)

    def test_reward_weights_change_by_prompt_category(self):
        fast = ModelCandidate(
            model="fast",
            provider="provider-fast",
            data_boundary="external",
            estimated_cost_usd=0.005,
            latency_ms_p95=200,
            quality_score=0.30,
            success_rate=0.70,
            sample_count=100,
        )
        accurate = ModelCandidate(
            model="accurate",
            provider="provider-accurate",
            data_boundary="external",
            estimated_cost_usd=0.10,
            latency_ms_p95=2_000,
            quality_score=0.99,
            success_rate=0.99,
            sample_count=100,
        )
        simple = self.optimizer.optimize(
            RoutingRequest(request_id="req-simple", task_type="simple"),
            (fast, accurate),
        )
        complex_result = self.optimizer.optimize(
            RoutingRequest(request_id="req-complex", task_type="complex"),
            (fast, accurate),
        )
        self.assertEqual("fast", simple.selected.model)
        self.assertEqual("accurate", complex_result.selected.model)
        self.assertIn("reward-category=complex", complex_result.explanation)


if __name__ == "__main__":
    unittest.main()
