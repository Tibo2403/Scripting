"""Tests for the optional Codex cost-routing wrapper."""

import importlib.util
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
