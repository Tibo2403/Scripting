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
        self.assertEqual(ROUTER.route_model("Corrige une typo dans le README")[0], "codex-cheap")
        self.assertEqual(ROUTER.route_model("Refactor this Python API")[0], "codex-strong")
        self.assertEqual(ROUTER.route_model("Audit sécurité production Supabase RLS")[0], "codex-strong")

    def test_route_model_matches_accented_french_keywords(self) -> None:
        self.assertEqual(ROUTER.route_model("Prépare un résumé du README")[0], "codex-cheap")
        self.assertEqual(ROUTER.route_model("Question de fiscalité pour Odoo")[0], "codex-strong")

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
            self.assertEqual(model, "codex-strong")
            self.assertIn("HF_TOKEN is missing", reason)

    def test_codex_provider_helpers_select_expected_profiles(self) -> None:
        self.assertEqual(ROUTER.codex_profile("litellm"), "cost-routing")
        self.assertEqual(ROUTER.codex_profile("huggingface"), "cost-routing-hf")
        self.assertEqual(ROUTER.codex_model("codex-hf-fast", "litellm"), "codex-hf-fast")
        self.assertEqual(
            ROUTER.codex_model("codex-hf-fast", "huggingface"),
            ROUTER.HF_DIRECT_MODEL,
        )

    def test_default_codex_provider_rejects_unknown_environment_value(self) -> None:
        with patch.dict(ROUTER.os.environ, {"CODEX_ROUTER_CODEX_PROVIDER": "unknown"}):
            self.assertEqual(ROUTER.default_codex_provider(), "litellm")

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
        codex_provider, codex_reason = ROUTER.codex_provider_from_policy(None, policy)
        self.assertEqual(codex_provider, "litellm")
        self.assertIn("policy default", codex_reason)
        self.assertEqual(
            ROUTER.fallback_order_from_policy(codex_provider, policy),
            ["litellm", "huggingface"],
        )

    def test_policy_open_models_only_prefers_hugging_face(self) -> None:
        policy = {**ROUTER.DEFAULT_POLICY, "open_models_only": True}
        self.assertEqual(ROUTER.provider_from_policy("Security review", None, policy)[0], "huggingface")
        self.assertEqual(ROUTER.codex_provider_from_policy(None, policy)[0], "huggingface")

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
