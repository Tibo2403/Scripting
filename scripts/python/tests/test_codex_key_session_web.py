"""Tests for the optional local web key session launcher."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock


MODULE_PATH = Path(__file__).resolve().parents[1] / "codex_key_session_web.py"
SPEC = importlib.util.spec_from_file_location("codex_key_session_web", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load codex_key_session_web.py")
WEB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WEB)


class KeySessionWebTests(unittest.TestCase):
    def test_parse_args_defaults_to_localhost(self) -> None:
        args = WEB.parse_args([])
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.ui_port, 8787)
        self.assertEqual(args.proxy_port, 4000)

    def test_log_message_is_suppressed(self) -> None:
        handler = object.__new__(WEB.KeySessionHandler)
        self.assertIsNone(handler.log_message("secret %s", "sk-test"))

    def test_stop_proxy_terminates_running_process(self) -> None:
        process = MagicMock()
        process.poll.return_value = None
        state = WEB.SessionState()
        state.process = process

        handler = object.__new__(WEB.KeySessionHandler)
        handler.state = state
        handler._stop_proxy("done")

        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=8)
        self.assertIsNone(state.process)
        self.assertEqual(state.message, "done")


if __name__ == "__main__":
    unittest.main()
