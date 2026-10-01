"""Tests for the optional Codex cost-routing wrapper."""

import importlib
import json
import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "codex_cost_router.py"
if str(MODULE_PATH.parent) not in sys.path:
    sys.path.insert(0, str(MODULE_PATH.parent))
ROUTER = importlib.import_module("codex_cost_router")
router_adaptive = importlib.import_module("codex_router_adaptive")
router_availability = importlib.import_module("codex_router_availability")
router_config = importlib.import_module("codex_router_config")
router_policy = importlib.import_module("codex_router_policy")
router_storage = importlib.import_module("codex_router_storage")


class CodexRouterAdaptiveTests(unittest.TestCase):
    def test_policy_file_can_configure_adaptive_router(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "policy.yaml"
            policy.write_text(
                "\n".join(
                    [
                        "adaptive_router:",
                        "  enabled: true",
                        "  shadow_mode: false",
                        "  min_confidence_delta: 0.25",
                        "  cost_guard_enabled: false",
                        "  max_cost_multiplier: 1.5",
                    ]
                ),
                encoding="utf-8",
            )
            loaded = router_policy.load_policy(policy)
        config = router_adaptive.adaptive_router_config(loaded)
        self.assertTrue(config["enabled"])
        self.assertFalse(config["shadow_mode"])
        self.assertEqual(config["min_confidence_delta"], 0.25)
        self.assertFalse(config["cost_guard_enabled"])
        self.assertEqual(config["max_cost_multiplier"], 1.5)

    def test_adaptive_router_shadow_mode_keeps_baseline_order(self) -> None:
        policy = {
            **router_config.DEFAULT_POLICY,
            "adaptive_router": {
                "enabled": True,
                "shadow_mode": True,
                "min_confidence_delta": 0.05,
            },
        }
        history = [
            {
                "codex_provider": "litellm",
                "ttft_ms": 9000,
                "latency_ms": 60000,
                "success": False,
            },
            {"codex_provider": "litellm", "error_rate": 1.0, "returncode": 1},
            {
                "codex_provider": "standard",
                "ttft_ms": 500,
                "latency_ms": 3000,
                "success": True,
            },
        ]
        decision = router_adaptive.adaptive_router_decision(
            ["litellm", "standard"], policy, history
        )
        self.assertEqual(decision["effective_order"], ["litellm", "standard"])
        self.assertEqual(decision["suggested_provider"], "standard")
        self.assertTrue(decision["would_switch"])
        self.assertFalse(decision["applied"])

    def test_adaptive_router_can_apply_markov_switch_when_enabled(self) -> None:
        policy = {
            **router_config.DEFAULT_POLICY,
            "adaptive_router": {
                "enabled": True,
                "shadow_mode": False,
                "min_confidence_delta": 0.05,
            },
        }
        history = [
            {
                "codex_provider": "litellm",
                "ttft_ms": 9000,
                "latency_ms": 60000,
                "success": False,
            },
            {"codex_provider": "litellm", "token_pressure": 1.0, "quality_score": 0.2},
            {
                "codex_provider": "standard",
                "ttft_ms": 500,
                "latency_ms": 3000,
                "success": True,
            },
        ]
        decision = router_adaptive.adaptive_router_decision(
            ["litellm", "standard"], policy, history
        )
        self.assertEqual(decision["effective_order"][0], "standard")
        self.assertTrue(decision["applied"])

    def test_adaptive_router_uses_performance_score_for_gain(self) -> None:
        policy = {
            **router_config.DEFAULT_POLICY,
            "adaptive_router": {
                "enabled": True,
                "shadow_mode": False,
                "min_confidence_delta": 0.05,
                "performance_weight": 0.6,
                "min_performance_observations": 2,
            },
        }
        history = [
            {
                "codex_provider": "litellm",
                "ttft_ms": 4_500,
                "latency_ms": 35_000,
                "estimated_cost_usd": 0.16,
                "quality_score": 0.82,
                "success": True,
            },
            {
                "codex_provider": "litellm",
                "ttft_ms": 4_200,
                "latency_ms": 32_000,
                "estimated_cost_usd": 0.15,
                "quality_score": 0.84,
                "success": True,
            },
            {
                "codex_provider": "standard",
                "ttft_ms": 700,
                "latency_ms": 4_000,
                "estimated_cost_usd": 0.03,
                "quality_score": 0.91,
                "success": True,
            },
            {
                "codex_provider": "standard",
                "ttft_ms": 800,
                "latency_ms": 4_300,
                "estimated_cost_usd": 0.035,
                "quality_score": 0.9,
                "success": True,
            },
        ]
        decision = router_adaptive.adaptive_router_decision(
            ["litellm", "standard"], policy, history
        )
        self.assertEqual(decision["effective_order"][0], "standard")
        self.assertGreater(decision["health"]["standard"]["performance_score"], 0.9)
        self.assertTrue(decision["applied"])

    def test_adaptive_router_cost_guard_blocks_expensive_noncritical_switch(
        self,
    ) -> None:
        policy = {
            **router_config.DEFAULT_POLICY,
            "adaptive_router": {
                "enabled": True,
                "shadow_mode": False,
                "min_confidence_delta": 0.05,
                "performance_weight": 0.6,
                "min_performance_observations": 2,
                "cost_guard_enabled": True,
                "max_cost_multiplier": 2.0,
                "critical_risk_threshold": 0.65,
            },
        }
        history = [
            {
                "codex_provider": "litellm",
                "ttft_ms": 2_800,
                "latency_ms": 16_000,
                "estimated_cost_usd": 0.018,
                "quality_score": 0.89,
                "error_rate": 0.01,
                "success": True,
            },
            {
                "codex_provider": "litellm",
                "ttft_ms": 2_700,
                "latency_ms": 15_000,
                "estimated_cost_usd": 0.018,
                "quality_score": 0.9,
                "error_rate": 0.0,
                "success": True,
            },
            {
                "codex_provider": "standard",
                "ttft_ms": 700,
                "latency_ms": 5_200,
                "estimated_cost_usd": 0.095,
                "quality_score": 0.9,
                "error_rate": 0.0,
                "success": True,
            },
            {
                "codex_provider": "standard",
                "ttft_ms": 750,
                "latency_ms": 5_000,
                "estimated_cost_usd": 0.095,
                "quality_score": 0.91,
                "error_rate": 0.0,
                "success": True,
            },
        ]
        decision = router_adaptive.adaptive_router_decision(
            ["litellm", "standard"], policy, history
        )
        self.assertEqual(decision["suggested_provider"], "standard")
        self.assertTrue(decision["would_switch"])
        self.assertTrue(decision["cost_guard_blocked"])
        self.assertFalse(decision["applied"])
        self.assertEqual(decision["effective_order"][0], "litellm")
        self.assertGreater(decision["cost_multiplier"], 5.0)

    def test_run_router_logs_active_provider_after_adaptive_switch(self) -> None:
        policy = {
            **router_config.DEFAULT_POLICY,
            "adaptive_router": {
                "enabled": True,
                "shadow_mode": False,
                "min_confidence_delta": 0.05,
            },
        }
        history = [
            {
                "codex_provider": "litellm",
                "ttft_ms": 9000,
                "latency_ms": 60000,
                "success": False,
            },
            {"codex_provider": "litellm", "error_rate": 1.0, "returncode": 1},
            {
                "codex_provider": "standard",
                "ttft_ms": 500,
                "latency_ms": 3000,
                "success": True,
            },
        ]
        args = argparse.Namespace(
            prompt=["Refactor this Python API"],
            max_input_tokens=router_config.DEFAULT_MAX_INPUT_TOKENS,
            policy=Path("unused-policy.yaml"),
            codex_provider="litellm",
            provider=None,
            force_model=None,
            max_output_tokens=router_config.DEFAULT_MAX_OUTPUT_TOKENS,
            dry_run=True,
            codex_arg=[],
        )
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            log_file = home / "logs" / "cost_router.jsonl"
            state_file = home / "logs" / "cost_router_state.json"
            with (
                patch.object(router_config, "LOG_DIR", home / "logs"),
                patch.object(router_config, "LOG_FILE", log_file),
                patch.object(router_config, "STATE_FILE", state_file),
                patch.object(router_policy, "load_policy", return_value=policy),
                patch.object(router_storage, "read_history", return_value=history),
                patch.object(
                    router_availability, "proxy_available", return_value=False
                ),
                patch.object(router_availability, "qwen_available", return_value=False),
            ):
                self.assertEqual(ROUTER.run_router(args), 0)
            record = json.loads(log_file.read_text(encoding="utf-8").splitlines()[0])
        self.assertTrue(record["adaptive_router"]["applied"])
        self.assertEqual(record["requested_codex_provider"], "litellm")
        self.assertEqual(record["codex_provider"], "standard")
        self.assertEqual(record["codex_profile"], "standard")


if __name__ == "__main__":
    unittest.main()
