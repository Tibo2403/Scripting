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
        self.assertEqual(ROUTER.route_model("Refactor this Python API")[0], "codex-auto")
        self.assertEqual(ROUTER.route_model("Audit sécurité production Supabase RLS")[0], "codex-strong")

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
