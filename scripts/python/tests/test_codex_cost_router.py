"""Tests for the optional Codex cost-routing wrapper."""

import importlib
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "codex_cost_router.py"
if str(MODULE_PATH.parent) not in sys.path:
    sys.path.insert(0, str(MODULE_PATH.parent))
router_availability = importlib.import_module("codex_router_availability")
router_config = importlib.import_module("codex_router_config")
router_policy = importlib.import_module("codex_router_policy")
router_prompt = importlib.import_module("codex_router_prompt")
router_providers = importlib.import_module("codex_router_providers")
router_selection = importlib.import_module("codex_router_selection")
router_storage = importlib.import_module("codex_router_storage")


class CodexRouterRoutingTests(unittest.TestCase):
    def test_clean_text_removes_html_and_duplicate_lines(self) -> None:
        text = "<p>Hello</p>\nHello\nHello\n\nWorld"
        self.assertEqual(router_prompt.clean_text(text), "Hello\n\nWorld")

    def test_compress_logs_removes_low_value_debug_lines(self) -> None:
        text = "DEBUG progress 1\nDEBUG progress 2\nERROR request failed"
        self.assertEqual(router_prompt.compress_logs(text), "ERROR request failed")

    def test_route_model_uses_expected_aliases(self) -> None:
        with (
            patch.object(router_availability, "phi_available", return_value=False),
            patch.object(router_availability, "claude_available", return_value=False),
            patch.object(router_availability, "proxy_available", return_value=False),
        ):
            self.assertEqual(
                router_selection.route_model("Corrige une typo dans le README")[0],
                "codex-light",
            )
            self.assertEqual(
                router_selection.route_model("Refactor this Python API")[0],
                "codex-default",
            )
            self.assertEqual(
                router_selection.route_model("Audit securite production Supabase RLS")[
                    0
                ],
                "codex-deep",
            )

    def test_route_model_can_use_phi_for_small_local_tasks(self) -> None:
        with patch.object(router_availability, "phi_available", return_value=True):
            model, reason = router_selection.route_model(
                "Corrige une typo dans le README", provider="local-small"
            )
        self.assertEqual(model, "codex-small-local")
        self.assertIn("64 output tokens", reason)

    def test_route_model_can_use_claude_for_complex_proxy_tasks(self) -> None:
        with (
            patch.object(router_availability, "claude_available", return_value=True),
            patch.object(router_availability, "proxy_available", return_value=True),
        ):
            model, reason = router_selection.route_model(
                "Audit securite production Supabase RLS", provider="claude"
            )
        self.assertEqual(model, "codex-claude-complex")
        self.assertIn("active LiteLLM proxy", reason)

    def test_default_policy_routes_simple_local_and_complex_claude(self) -> None:
        self.assertEqual(
            router_providers.provider_from_policy(
                "Corrige une typo dans le README", None, router_config.DEFAULT_POLICY
            )[0],
            "local-small",
        )
        self.assertEqual(
            router_providers.provider_from_policy(
                "Audit securite production Supabase RLS",
                None,
                router_config.DEFAULT_POLICY,
            )[0],
            "claude",
        )

    def test_route_model_matches_accented_french_keywords(self) -> None:
        self.assertEqual(
            router_selection.route_model("Prepare un resume du README")[0],
            "codex-light",
        )
        self.assertEqual(
            router_selection.route_model("Question de fiscalite pour Odoo")[0],
            "codex-deep",
        )

    def test_hybrid_classifier_detects_semantic_operational_risk(self) -> None:
        category, reason = router_prompt.classify_complexity(
            "Une fuite mÃƒÆ’Ã‚Â©moire intermittente apparaÃƒÆ’Ã‚Â®t sous forte charge"
        )
        self.assertEqual(category, "complex")
        self.assertIn("hybrid category=complex", reason)
        self.assertIn("risk=", reason)

    def test_phi_throughput_guard_switches_to_qwen(self) -> None:
        history = [
            {
                "execution_mode": "codex-exec",
                "model": router_config.SMALL_LOCAL_MODEL,
                "success": True,
                "tokens_per_second": 2.5,
            }
        ]
        with (
            patch.object(router_availability, "phi_available", return_value=True),
            patch.object(router_availability, "qwen_available", return_value=True),
            patch.object(router_storage, "read_history", return_value=history),
        ):
            model, reason = router_providers.select_local_small_model("simple task")
        self.assertEqual(model, router_config.QWEN_LOCAL_MODEL)
        self.assertIn("below 5.00 tok/s", reason)

    def test_route_model_sends_long_context_to_gemini_biased_alias(self) -> None:
        self.assertEqual(
            router_selection.route_model(
                "Analyse ces logs et fais une synthese long context"
            )[0],
            "codex-long",
        )
        self.assertEqual(
            router_selection.route_model(
                "Summarize this large file", provider="gemini"
            )[0],
            "codex-long",
        )

    def test_route_model_can_prefer_hugging_face_when_token_exists(self) -> None:
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test"}):
            self.assertEqual(
                router_selection.route_model(
                    "Benchmark Hugging Face multi-provider routing"
                )[0],
                "codex-hf-fast",
            )
            self.assertEqual(
                router_selection.route_model(
                    "Corrige une typo dans le README", provider="huggingface"
                )[0],
                "codex-hf-cheap",
            )

    def test_route_model_falls_back_when_hugging_face_token_is_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            model, reason = router_selection.route_model(
                "Use Hugging Face providers", provider="huggingface"
            )
            self.assertEqual(model, "codex-default")
            self.assertIn("HF_TOKEN is missing", reason)

    def test_route_model_can_use_local_qwen_when_ollama_is_reachable(self) -> None:
        with (
            patch.dict(os.environ, {"QWEN_API_BASE": "https://ignored.example/v1"}),
            patch.object(socket, "create_connection"),
        ):
            self.assertEqual(
                router_selection.route_model(
                    "Use qwen ollama as backup", provider="qwen"
                )[0],
                "codex-qwen-local",
            )
            self.assertEqual(
                router_selection.route_model("Prefer local llm fallback")[0],
                "codex-qwen-local",
            )

    def test_route_model_can_avoid_openai_with_gemini_qwen_alias(self) -> None:
        with patch.object(socket, "create_connection"):
            model, reason = router_selection.route_model(
                "Refactor this Python API", provider="no-openai"
            )
        self.assertEqual(model, "codex-no-openai")
        self.assertIn("OpenAI avoided", reason)

    def test_route_model_falls_back_when_qwen_endpoint_is_missing(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(socket, "create_connection", side_effect=OSError),
        ):
            model, reason = router_selection.route_model(
                "Use Qwen local", provider="qwen"
            )
            self.assertEqual(model, "codex-default")
            self.assertIn("Ollama is not listening", reason)

    def test_codex_provider_helpers_select_expected_profiles(self) -> None:
        self.assertEqual(router_providers.codex_profile("standard"), "standard")
        self.assertEqual(router_providers.codex_profile("litellm"), "cost-routing")
        self.assertEqual(
            router_providers.codex_profile("huggingface"), "cost-routing-hf"
        )
        self.assertEqual(
            router_providers.codex_model("codex-hf-fast", "litellm"), "codex-hf-fast"
        )
        self.assertEqual(
            router_providers.codex_model("codex-hf-fast", "huggingface"),
            router_config.HF_DIRECT_MODEL,
        )

    def test_default_codex_provider_rejects_unknown_environment_value(self) -> None:
        with patch.dict(os.environ, {"CODEX_ROUTER_CODEX_PROVIDER": "unknown"}):
            self.assertEqual(router_providers.default_codex_provider(), "auto")

    def test_profile_block_includes_optional_hugging_face_profile(self) -> None:
        self.assertIn("[model_providers.huggingface]", router_config.PROFILE_BLOCK)
        self.assertIn("[profiles.cost-routing-hf]", router_config.PROFILE_BLOCK)
        self.assertIn('model = "codex-default"', router_config.COST_ROUTING_PROFILE)
        self.assertIn(
            'model = "openai/gpt-oss-120b:fastest"',
            router_config.COST_ROUTING_HF_PROFILE,
        )

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
            loaded = router_policy.load_policy(policy)
        self.assertEqual(loaded["default_provider"], "openai")
        self.assertEqual(loaded["default_codex_provider"], "huggingface")
        self.assertEqual(loaded["task_provider_rules"]["medium"], "openai")
        self.assertEqual(loaded["fallback_order"], ["huggingface", "litellm"])

    def test_policy_resolves_provider_and_fallback_order(self) -> None:
        policy = {
            **router_config.DEFAULT_POLICY,
            "task_provider_rules": {"simple": "huggingface", "medium": "openai"},
            "fallback_order": ["huggingface", "litellm"],
        }
        provider, reason = router_providers.provider_from_policy(
            "Document this README", None, policy
        )
        self.assertEqual(provider, "huggingface")
        self.assertIn("policy task rule", reason)
        with patch.object(router_availability, "proxy_available", return_value=True):
            codex_provider, codex_reason = router_providers.codex_provider_from_policy(
                None, policy
            )
        self.assertEqual(codex_provider, "litellm")
        self.assertIn("LiteLLM proxy detected", codex_reason)
        self.assertEqual(
            router_providers.fallback_order_from_policy(codex_provider, policy),
            ["litellm", "huggingface", "standard"],
        )

    def test_proxy_expansion_keeps_standard_first_for_normal_traffic(self) -> None:
        policy = {
            **router_config.DEFAULT_POLICY,
            "fallback_order": ["litellm", "standard", "huggingface"],
        }
        order = router_providers.traffic_preserving_fallback_order(
            "litellm",
            "auto",
            router_config.DEFAULT_MODEL,
            policy,
        )
        self.assertEqual(order, ["standard", "litellm", "huggingface"])

    def test_proxy_routes_stay_first_for_claude_and_gemini_requests(self) -> None:
        policy = {
            **router_config.DEFAULT_POLICY,
            "fallback_order": ["standard", "litellm", "huggingface"],
        }
        self.assertEqual(
            router_providers.traffic_preserving_fallback_order(
                "standard",
                "claude",
                router_config.CLAUDE_COMPLEX_MODEL,
                policy,
            )[0],
            "litellm",
        )
        self.assertEqual(
            router_providers.traffic_preserving_fallback_order(
                "standard",
                "gemini",
                router_config.LONG_MODEL,
                policy,
            )[0],
            "litellm",
        )

    def test_policy_open_models_only_prefers_hugging_face(self) -> None:
        policy = {**router_config.DEFAULT_POLICY, "open_models_only": True}
        self.assertEqual(
            router_providers.provider_from_policy("Security review", None, policy)[0],
            "huggingface",
        )
        self.assertEqual(
            router_providers.codex_provider_from_policy(None, policy)[0], "huggingface"
        )

    def test_policy_or_environment_can_avoid_openai(self) -> None:
        policy = {**router_config.DEFAULT_POLICY, "avoid_openai": True}
        provider, reason = router_providers.provider_from_policy(
            "Refactor this Python API", None, policy
        )
        self.assertEqual(provider, "no-openai")
        self.assertIn("OpenAI avoidance", reason)
        with patch.dict(os.environ, {"CODEX_ROUTER_OPENAI_MODE": "avoid"}):
            provider, reason = router_providers.provider_from_policy(
                "Refactor this Python API", None, router_config.DEFAULT_POLICY
            )
        self.assertEqual(provider, "no-openai")
        self.assertIn("OpenAI avoidance", reason)

    def test_build_optimized_prompt_respects_budget(self) -> None:
        context = (
            "<div>"
            + ("Architecture production Odoo migration security. " * 1000)
            + "</div>"
        )
        optimized = router_prompt.build_optimized_prompt(context, 120)
        self.assertLessEqual(router_prompt.estimate_tokens(optimized), 120)
        self.assertNotIn("<div>", optimized)
        self.assertIn("context truncated", optimized)

    def test_proxy_available_returns_false_when_connection_fails(self) -> None:
        with patch.object(socket, "create_connection", side_effect=OSError):
            self.assertFalse(router_availability.proxy_available())

    def test_litellm_disable_env_bypasses_proxy(self) -> None:
        with (
            patch.dict(os.environ, {"CODEX_ROUTER_DISABLE_LITELLM": "1"}, clear=False),
            patch.object(socket, "create_connection") as create_connection,
        ):
            self.assertFalse(router_availability.proxy_available())
            provider, reason = router_providers.codex_provider_from_policy(
                "litellm", router_config.DEFAULT_POLICY
            )
            ready, detail = router_providers.codex_provider_ready("litellm")

        create_connection.assert_not_called()
        self.assertEqual(provider, "standard")
        self.assertIn("bypassed", reason)
        self.assertFalse(ready)
        self.assertIn("disabled", detail)


if __name__ == "__main__":
    unittest.main()
