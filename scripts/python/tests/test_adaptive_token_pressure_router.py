"""Tests for LiteLLM-independent adaptive token pressure routing."""

import importlib.util
import inspect
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "adaptive_token_pressure_router.py"
if str(MODULE_PATH.parent) not in sys.path:
    sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("adaptive_token_pressure_router", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load adaptive_token_pressure_router.py")
ROUTER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ROUTER
SPEC.loader.exec_module(ROUTER)


class AdaptiveTokenPressureRouterTests(unittest.TestCase):
    def test_module_does_not_import_litellm_core(self) -> None:
        source = inspect.getsource(ROUTER)
        self.assertNotIn("import litellm", source)
        self.assertNotIn("from litellm", source)

    def test_estimate_tpm_rpm_risk_increases_with_pressure(self) -> None:
        quiet = ROUTER.estimate_tpm_rpm_risk(
            prompt_tokens=500,
            response_tokens=100,
            in_flight=0,
            tpm_limit=100_000,
            rpm_limit=60,
            observed_tpm=1_000,
            observed_rpm=2,
        )
        busy = ROUTER.estimate_tpm_rpm_risk(
            prompt_tokens=50_000,
            response_tokens=5_000,
            in_flight=4,
            tpm_limit=100_000,
            rpm_limit=60,
            observed_tpm=90_000,
            observed_rpm=55,
        )
        self.assertLess(quiet["quota_risk"], busy["quota_risk"])
        self.assertGreater(busy["tpm_pressure"], 0.9)
        self.assertGreater(busy["rpm_pressure"], 0.9)

    def test_choose_adaptive_route_prefers_lower_cost_and_pressure(self) -> None:
        decision = ROUTER.choose_adaptive_route(
            ["cheap-safe", "expensive-busy"],
            {
                "cheap-safe": {
                    "cost": 0.05,
                    "ewma_error_rate": 0.0,
                    "ewma_token_pressure": 0.05,
                    "tpm_limit": 200_000,
                    "rpm_limit": 120,
                },
                "expensive-busy": {
                    "cost": 0.60,
                    "ewma_error_rate": 0.1,
                    "ewma_token_pressure": 0.85,
                    "tpm_limit": 20_000,
                    "rpm_limit": 30,
                    "ewma_tpm": 19_000,
                    "ewma_rpm": 28,
                },
            },
            prompt_tokens=2_000,
            dry_run=True,
        )
        self.assertTrue(decision["dry_run"])
        self.assertEqual(decision["selected_model"], "cheap-safe")
        self.assertEqual(decision["scores"][0]["model"], "cheap-safe")

    def test_update_pressure_state_marks_429_as_overload(self) -> None:
        metrics = {"ewma_token_pressure": 0.0, "ewma_rpm_pressure": 0.0}
        ROUTER.update_pressure_state(metrics, prompt_tokens=1_000, response_tokens=0, status=429, queue_depth=2)
        self.assertGreater(metrics["ewma_token_pressure"], 0.0)
        self.assertGreater(metrics["ewma_rpm_pressure"], 0.0)
        self.assertGreater(ROUTER.markov_overload_risk(metrics), 0.0)


if __name__ == "__main__":
    unittest.main()
