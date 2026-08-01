"""Tests for the risk-adjusted LiteLLM front router."""

import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.python import risk_adjusted_router as ROUTER  # noqa: E402


class RiskAdjustedRouterStateTests(unittest.TestCase):
    def test_load_state_preserves_non_object_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "risk-router-state.json"
            state_path.write_text("[1, 2, 3]", encoding="utf-8")

            with patch.object(ROUTER, "STATE_PATH", state_path):
                state = ROUTER.load_state_unlocked()

            backups = list(state_path.parent.glob("risk-router-state.json.invalid-*"))

            self.assertEqual(state, {"models": {}, "requests": []})
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "[1, 2, 3]")

    def test_update_state_recovers_invalid_collection_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "risk-router-state.json"
            state_path.write_text(
                json.dumps({"models": [], "requests": {"bad": "shape"}}),
                encoding="utf-8",
            )

            def mutate(state: dict[str, object]) -> None:
                ROUTER.ensure_model_state(state, "codex-qwen-local")
                ROUTER.append_request(state, {"selected_model": "codex-qwen-local"})

            with patch.object(ROUTER, "STATE_PATH", state_path):
                state = ROUTER.update_state(mutate)

            backups = list(state_path.parent.glob("risk-router-state.json.invalid-*"))

            self.assertIn("codex-qwen-local", state["models"])
            self.assertEqual(state["requests"], [{"selected_model": "codex-qwen-local"}])
            self.assertEqual(len(backups), 1)


class RiskAdjustedRouterNetworkTests(unittest.TestCase):
    def test_forward_json_sanitizes_upstream_network_errors(self) -> None:
        handler = ROUTER.Handler.__new__(ROUTER.Handler)
        handler.headers = {}

        with patch.object(ROUTER.urllib.request, "urlopen", side_effect=urllib.error.URLError("secret-token")):
            status, headers, body, error = handler.forward_json("/v1/chat/completions", {"model": "codex-default"})

        self.assertEqual(status, 502)
        self.assertEqual(headers, [])
        self.assertEqual(json.loads(body.decode("utf-8")), {"error": "upstream request failed"})
        self.assertEqual(error, "URLError")
        self.assertNotIn("secret-token", body.decode("utf-8"))

    def test_forward_json_does_not_swallow_programming_errors(self) -> None:
        handler = ROUTER.Handler.__new__(ROUTER.Handler)
        handler.headers = {}

        with patch.object(ROUTER.urllib.request, "urlopen", side_effect=ValueError("bad test setup")):
            with self.assertRaises(ValueError):
                handler.forward_json("/v1/chat/completions", {"model": "codex-default"})

if __name__ == "__main__":
    unittest.main()
