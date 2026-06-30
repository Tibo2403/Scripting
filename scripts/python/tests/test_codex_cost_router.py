"""Tests for the optional Codex cost-routing wrapper."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "codex_cost_router.py"
SPEC = importlib.util.spec_from_file_location("codex_cost_router", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load codex_cost_router.py")
ROUTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTER)


class CodexCostRouterTests(unittest.TestCase):
    def test_clean_text_removes_html_and_duplicate_lines(self) -> None:
        text = "<p>Hello</p>\nHello\nHello\n\nWorld"
        self.assertEqual(ROUTER.clean_text(text), "Hello\n\nWorld")

    def test_compress_logs_removes_low_value_debug_lines(self) -> None:
        text = "DEBUG progress 1\nDEBUG progress 2\nERROR request failed"
        self.assertEqual(ROUTER.compress_logs(text), "ERROR request failed")

    def test_route_model_uses_expected_aliases(self) -> None:
        self.assertEqual(ROUTER.route_model("Corrige une typo dans le README")[0], "codex-light")
        self.assertEqual(ROUTER.route_model("Refactor this Python API")[0], "codex-default")
        self.assertEqual(ROUTER.route_model("Audit securite production Supabase RLS")[0], "codex-deep")

    def test_route_model_matches_accented_french_keywords(self) -> None:
        self.assertEqual(ROUTER.route_model("Prepare un resume du README")[0], "codex-light")
        self.assertEqual(ROUTER.route_model("Question de fiscalite pour Odoo")[0], "codex-deep")

    def test_route_model_sends_long_context_to_gemini_biased_alias(self) -> None:
        self.assertEqual(
            ROUTER.route_model("Analyse ces logs et fais une synthese long context")[0],
            "codex-long",
        )
        self.assertEqual(
            ROUTER.route_model("Summarize this large file", provider="gemini")[0],
            "codex-long",
        )

    def test_route_model_can_prefer_hugging_face_when_token_exists(self) -> None:
        with patch.dict(ROUTER.os.environ, {"HF_TOKEN": "hf_test"}):
            self.assertEqual(
                ROUTER.route_model("Benchmark Hugging Face multi-provider routing")[0],
                "codex-hf-fast",
            )
            self.assertEqual(
                ROUTER.route_model("Corrige une typo dans le README", provider="huggingface")[0],
                "codex-hf-cheap",
            )

    def test_route_model_falls_back_when_hugging_face_token_is_missing(self) -> None:
        with patch.dict(ROUTER.os.environ, {}, clear=True):
            model, reason = ROUTER.route_model("Use Hugging Face providers", provider="huggingface")
            self.assertEqual(model, "codex-default")
            self.assertIn("HF_TOKEN is missing", reason)

    def test_route_model_can_use_local_qwen_when_ollama_is_reachable(self) -> None:
        with (
            patch.dict(ROUTER.os.environ, {"QWEN_API_BASE": "https://ignored.example/v1"}),
            patch.object(ROUTER.socket, "create_connection"),
        ):
            self.assertEqual(
                ROUTER.route_model("Use qwen ollama as backup", provider="qwen")[0],
                "codex-qwen-local",
            )
            self.assertEqual(
                ROUTER.route_model("Prefer local llm fallback")[0],
                "codex-qwen-local",
            )

    def test_route_model_can_avoid_openai_with_gemini_qwen_alias(self) -> None:
        with patch.object(ROUTER.socket, "create_connection"):
            model, reason = ROUTER.route_model("Refactor this Python API", provider="no-openai")
        self.assertEqual(model, "codex-no-openai")
        self.assertIn("OpenAI avoided", reason)

    def test_route_model_falls_back_when_qwen_endpoint_is_missing(self) -> None:
        with patch.dict(ROUTER.os.environ, {}, clear=True), patch.object(
            ROUTER.socket, "create_connection", side_effect=OSError
        ):
            model, reason = ROUTER.route_model("Use Qwen local", provider="qwen")
            self.assertEqual(model, "codex-default")
            self.assertIn("Ollama is not listening", reason)

    def test_codex_provider_helpers_select_expected_profiles(self) -> None:
        self.assertEqual(ROUTER.codex_profile("standard"), "standard")
        self.assertEqual(ROUTER.codex_profile("litellm"), "cost-routing")
        self.assertEqual(ROUTER.codex_profile("huggingface"), "cost-routing-hf")
        self.assertEqual(ROUTER.codex_model("codex-hf-fast", "litellm"), "codex-hf-fast")
        self.assertEqual(
            ROUTER.codex_model("codex-hf-fast", "huggingface"),
            ROUTER.HF_DIRECT_MODEL,
        )

    def test_default_codex_provider_rejects_unknown_environment_value(self) -> None:
        with patch.dict(ROUTER.os.environ, {"CODEX_ROUTER_CODEX_PROVIDER": "unknown"}):
            self.assertEqual(ROUTER.default_codex_provider(), "auto")

    def test_profile_block_includes_optional_hugging_face_profile(self) -> None:
        self.assertIn("[model_providers.huggingface]", ROUTER.PROFILE_BLOCK)
        self.assertIn("[profiles.cost-routing-hf]", ROUTER.PROFILE_BLOCK)

    def test_policy_file_can_override_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "policy.yaml"
            policy.write_text(
                "\n".join(
                    [
                        "default_provider: openai",
                        "default_codex_provider: huggingface",
                        "open_models_only: false",
                        "task_provider_rules:",
                        "  simple: huggingface",
                        "  medium: openai",
                        "fallback_order:",
                        "  - huggingface",
                        "  - litellm",
                    ]
                ),
                encoding="utf-8",
            )
            loaded = ROUTER.load_policy(policy)
        self.assertEqual(loaded["default_provider"], "openai")
        self.assertEqual(loaded["default_codex_provider"], "huggingface")
        self.assertEqual(loaded["task_provider_rules"]["medium"], "openai")
        self.assertEqual(loaded["fallback_order"], ["huggingface", "litellm"])

    def test_policy_resolves_provider_and_fallback_order(self) -> None:
        policy = {
            **ROUTER.DEFAULT_POLICY,
            "task_provider_rules": {"simple": "huggingface", "medium": "openai"},
            "fallback_order": ["huggingface", "litellm"],
        }
        provider, reason = ROUTER.provider_from_policy("Document this README", None, policy)
        self.assertEqual(provider, "huggingface")
        self.assertIn("policy task rule", reason)
        with patch.object(ROUTER, "proxy_available", return_value=True):
            codex_provider, codex_reason = ROUTER.codex_provider_from_policy(None, policy)
        self.assertEqual(codex_provider, "litellm")
        self.assertIn("LiteLLM proxy detected", codex_reason)
        self.assertEqual(
            ROUTER.fallback_order_from_policy(codex_provider, policy),
            ["litellm", "huggingface", "standard"],
        )

    def test_policy_open_models_only_prefers_hugging_face(self) -> None:
        policy = {**ROUTER.DEFAULT_POLICY, "open_models_only": True}
        self.assertEqual(ROUTER.provider_from_policy("Security review", None, policy)[0], "huggingface")
        self.assertEqual(ROUTER.codex_provider_from_policy(None, policy)[0], "huggingface")

    def test_policy_or_environment_can_avoid_openai(self) -> None:
        policy = {**ROUTER.DEFAULT_POLICY, "avoid_openai": True}
        provider, reason = ROUTER.provider_from_policy("Refactor this Python API", None, policy)
        self.assertEqual(provider, "no-openai")
        self.assertIn("OpenAI avoidance", reason)
        with patch.dict(ROUTER.os.environ, {"CODEX_ROUTER_OPENAI_MODE": "avoid"}):
            provider, reason = ROUTER.provider_from_policy("Refactor this Python API", None, ROUTER.DEFAULT_POLICY)
        self.assertEqual(provider, "no-openai")
        self.assertIn("OpenAI avoidance", reason)

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
            loaded = ROUTER.load_policy(policy)
        config = ROUTER.adaptive_router_config(loaded)
        self.assertTrue(config["enabled"])
        self.assertFalse(config["shadow_mode"])
        self.assertEqual(config["min_confidence_delta"], 0.25)
        self.assertFalse(config["cost_guard_enabled"])
        self.assertEqual(config["max_cost_multiplier"], 1.5)

    def test_adaptive_router_shadow_mode_keeps_baseline_order(self) -> None:
        policy = {
            **ROUTER.DEFAULT_POLICY,
            "adaptive_router": {"enabled": True, "shadow_mode": True, "min_confidence_delta": 0.05},
        }
        history = [
            {"codex_provider": "litellm", "ttft_ms": 9000, "latency_ms": 60000, "success": False},
            {"codex_provider": "litellm", "error_rate": 1.0, "returncode": 1},
            {"codex_provider": "standard", "ttft_ms": 500, "latency_ms": 3000, "success": True},
        ]
        decision = ROUTER.adaptive_router_decision(["litellm", "standard"], policy, history)
        self.assertEqual(decision["effective_order"], ["litellm", "standard"])
        self.assertEqual(decision["suggested_provider"], "standard")
        self.assertTrue(decision["would_switch"])
        self.assertFalse(decision["applied"])

    def test_adaptive_router_can_apply_markov_switch_when_enabled(self) -> None:
        policy = {
            **ROUTER.DEFAULT_POLICY,
            "adaptive_router": {"enabled": True, "shadow_mode": False, "min_confidence_delta": 0.05},
        }
        history = [
            {"codex_provider": "litellm", "ttft_ms": 9000, "latency_ms": 60000, "success": False},
            {"codex_provider": "litellm", "token_pressure": 1.0, "quality_score": 0.2},
            {"codex_provider": "standard", "ttft_ms": 500, "latency_ms": 3000, "success": True},
        ]
        decision = ROUTER.adaptive_router_decision(["litellm", "standard"], policy, history)
        self.assertEqual(decision["effective_order"][0], "standard")
        self.assertTrue(decision["applied"])

    def test_adaptive_router_uses_performance_score_for_gain(self) -> None:
        policy = {
            **ROUTER.DEFAULT_POLICY,
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
        decision = ROUTER.adaptive_router_decision(["litellm", "standard"], policy, history)
        self.assertEqual(decision["effective_order"][0], "standard")
        self.assertGreater(decision["health"]["standard"]["performance_score"], 0.9)
        self.assertTrue(decision["applied"])

    def test_adaptive_router_cost_guard_blocks_expensive_noncritical_switch(self) -> None:
        policy = {
            **ROUTER.DEFAULT_POLICY,
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
        decision = ROUTER.adaptive_router_decision(["litellm", "standard"], policy, history)
        self.assertEqual(decision["suggested_provider"], "standard")
        self.assertTrue(decision["would_switch"])
        self.assertTrue(decision["cost_guard_blocked"])
        self.assertFalse(decision["applied"])
        self.assertEqual(decision["effective_order"][0], "litellm")
        self.assertGreater(decision["cost_multiplier"], 5.0)

    def test_build_optimized_prompt_respects_budget(self) -> None:
        context = "<div>" + ("Architecture production Odoo migration security. " * 1000) + "</div>"
        optimized = ROUTER.build_optimized_prompt(context, 120)
        self.assertLessEqual(ROUTER.estimate_tokens(optimized), 120)
        self.assertNotIn("<div>", optimized)
        self.assertIn("context truncated", optimized)

    def test_remove_profile_block_preserves_unrelated_configuration(self) -> None:
        config = "[features]\njs_repl = false\n\n" + ROUTER.PROFILE_BLOCK
        self.assertEqual(
            ROUTER.remove_profile_block(config),
            "[features]\njs_repl = false\n",
        )

    def test_proxy_available_returns_false_when_connection_fails(self) -> None:
        with patch.object(ROUTER.socket, "create_connection", side_effect=OSError):
            self.assertFalse(ROUTER.proxy_available())

    def test_find_litellm_uses_configured_existing_path(self) -> None:
        with tempfile.NamedTemporaryFile() as executable:
            with patch.dict(ROUTER.os.environ, {"LITELLM_CLI_PATH": executable.name}):
                self.assertEqual(ROUTER.find_litellm(), executable.name)

    def test_enable_disable_restores_original_config_bytes(self) -> None:
        initial = b"[features]\r\njs_repl = false\r\n"
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config = home / "config.toml"
            config.write_bytes(initial)
            with (
                patch.object(ROUTER, "CODEX_HOME", home),
                patch.object(ROUTER, "CODEX_CONFIG", config),
                patch.object(ROUTER, "LOG_DIR", home / "logs"),
                patch.object(ROUTER, "LOG_FILE", home / "logs" / "cost_router.jsonl"),
                patch.object(ROUTER, "STATE_FILE", home / "logs" / "cost_router_state.json"),
                patch.object(ROUTER, "CONFIG_BACKUP", home / "logs" / "config.toml.cost_router_backup"),
            ):
                ROUTER.enable_router()
                ROUTER.disable_router()
            self.assertEqual(config.read_bytes(), initial)


if __name__ == "__main__":
    unittest.main()
