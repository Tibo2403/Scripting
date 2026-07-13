"""Tests for the optional local web key session launcher."""

import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


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

    def test_start_proxy_exports_hf_token_under_litellm_mapping_name(self) -> None:
        handler = object.__new__(WEB.KeySessionHandler)
        handler.state = WEB.SessionState()
        handler.config_path = Path("config.yaml")
        handler.litellm_path = Path("litellm.exe")
        handler.proxy_host = "127.0.0.1"
        handler.proxy_port = 4000
        handler._read_form = MagicMock(  # type: ignore[method-assign]
            return_value={
                "OPENAI_API_KEY": "",
                "GEMINI_API_KEY": "",
                "HF_TOKEN": "hf_test",
                "USE_LOCAL_QWEN": "",
            }
        )
        handler._stop_proxy = MagicMock()  # type: ignore[method-assign]
        handler._send_page = MagicMock()  # type: ignore[method-assign]

        process = MagicMock()
        process.poll.return_value = None
        captured_env: dict[str, str] = {}

        def fake_popen(*args: object, **kwargs: object) -> MagicMock:
            captured_env.update(kwargs["env"])  # type: ignore[index]
            return process

        with (
            patch.object(WEB.subprocess, "Popen", side_effect=fake_popen),
            patch.object(WEB, "wait_for_port", return_value=True),
            patch.dict(os.environ, {}, clear=True),
        ):
            handler._start_proxy()

        self.assertEqual(captured_env["HF_TOKEN"], "hf_test")
        self.assertEqual(captured_env["HUGGINGFACE_API_KEY"], "hf_test")
        self.assertIn("Hugging Face", handler.state.message)

    def test_start_proxy_allows_qwen_local_without_cloud_keys(self) -> None:
        handler = object.__new__(WEB.KeySessionHandler)
        handler.state = WEB.SessionState()
        handler.config_path = Path("config.yaml")
        handler.litellm_path = Path("litellm.exe")
        handler.proxy_host = "127.0.0.1"
        handler.proxy_port = 4000
        handler._read_form = MagicMock(  # type: ignore[method-assign]
            return_value={
                "OPENAI_API_KEY": "",
                "GEMINI_API_KEY": "",
                "HF_TOKEN": "",
                "USE_LOCAL_QWEN": "1",
            }
        )
        handler._stop_proxy = MagicMock()  # type: ignore[method-assign]
        handler._send_page = MagicMock()  # type: ignore[method-assign]

        process = MagicMock()
        process.poll.return_value = None

        with (
            patch.object(WEB.subprocess, "Popen", return_value=process),
            patch.object(WEB, "wait_for_port", return_value=True),
            patch.dict(os.environ, {}, clear=True),
        ):
            handler._start_proxy()

        self.assertIn("Qwen local", handler.state.message)

    def test_start_proxy_reports_missing_litellm_before_spawn(self) -> None:
        handler = object.__new__(WEB.KeySessionHandler)
        handler.state = WEB.SessionState()
        handler.config_path = Path("config.yaml")
        handler.litellm_path = None
        handler.proxy_host = "127.0.0.1"
        handler.proxy_port = 4000
        handler._read_form = MagicMock(  # type: ignore[method-assign]
            return_value={
                "OPENAI_API_KEY": "",
                "GEMINI_API_KEY": "",
                "HF_TOKEN": "",
                "USE_LOCAL_QWEN": "1",
            }
        )
        handler._stop_proxy = MagicMock()  # type: ignore[method-assign]
        handler._send_page = MagicMock()  # type: ignore[method-assign]

        handler._start_proxy()

        handler._stop_proxy.assert_not_called()
        handler._send_page.assert_called_once()
        self.assertEqual(handler.state.message, "LiteLLM executable not found. Install LiteLLM first.")

    def test_run_server_starts_ui_when_litellm_is_missing(self) -> None:
        args = WEB.parse_args(["--config", str(Path("config.yaml"))])
        server = MagicMock()
        server.serve_forever.side_effect = KeyboardInterrupt

        with (
            patch.object(WEB, "find_litellm", side_effect=FileNotFoundError("LiteLLM executable not found. Install LiteLLM first.")),
            patch.object(WEB, "ThreadingHTTPServer", return_value=server),
        ):
            result = WEB.run_server(args)

        self.assertEqual(result, 0)
        self.assertIsNone(WEB.KeySessionHandler.litellm_path)
        server.serve_forever.assert_called_once()
        server.server_close.assert_called_once()

    def test_page_does_not_accept_qwen_api_fields(self) -> None:
        self.assertNotIn("QWEN_API_BASE", WEB.PAGE)
        self.assertNotIn("QWEN_API_KEY", WEB.PAGE)
        self.assertIn("local Ollama fallback", WEB.PAGE)

    def test_start_proxy_ignores_submitted_qwen_api_fields(self) -> None:
        handler = object.__new__(WEB.KeySessionHandler)
        handler.state = WEB.SessionState()
        handler.config_path = Path("config.yaml")
        handler.litellm_path = Path("litellm.exe")
        handler.proxy_host = "127.0.0.1"
        handler.proxy_port = 4000
        handler._read_form = MagicMock(  # type: ignore[method-assign]
            return_value={
                "OPENAI_API_KEY": "sk-test",
                "GEMINI_API_KEY": "",
                "HF_TOKEN": "",
                "USE_LOCAL_QWEN": "",
                "QWEN_API_BASE": "https://example.invalid/v1",
                "QWEN_API_KEY": "qwen-secret",
            }
        )
        handler._stop_proxy = MagicMock()  # type: ignore[method-assign]
        handler._send_page = MagicMock()  # type: ignore[method-assign]

        process = MagicMock()
        captured_env: dict[str, str] = {}

        def fake_popen(*args: object, **kwargs: object) -> MagicMock:
            captured_env.update(kwargs["env"])  # type: ignore[index]
            return process

        with (
            patch.object(WEB.subprocess, "Popen", side_effect=fake_popen),
            patch.object(WEB, "wait_for_port", return_value=True),
            patch.dict(os.environ, {}, clear=True),
        ):
            handler._start_proxy()

        self.assertNotIn("QWEN_API_BASE", captured_env)
        self.assertNotIn("QWEN_API_KEY", captured_env)
        self.assertIn("OpenAI", handler.state.message)

    def test_start_proxy_does_not_inherit_shell_provider_keys(self) -> None:
        handler = object.__new__(WEB.KeySessionHandler)
        handler.state = WEB.SessionState()
        handler.config_path = Path("config.yaml")
        handler.litellm_path = Path("litellm.exe")
        handler.proxy_host = "127.0.0.1"
        handler.proxy_port = 4000
        handler._read_form = MagicMock(  # type: ignore[method-assign]
            return_value={
                "OPENAI_API_KEY": "",
                "GEMINI_API_KEY": "",
                "HF_TOKEN": "",
                "USE_LOCAL_QWEN": "1",
            }
        )
        handler._stop_proxy = MagicMock()  # type: ignore[method-assign]
        handler._send_page = MagicMock()  # type: ignore[method-assign]

        process = MagicMock()
        captured_env: dict[str, str] = {}

        def fake_popen(*args: object, **kwargs: object) -> MagicMock:
            captured_env.update(kwargs["env"])  # type: ignore[index]
            return process

        with (
            patch.object(WEB.subprocess, "Popen", side_effect=fake_popen),
            patch.object(WEB, "wait_for_port", return_value=True),
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "shell-openai",
                    "GEMINI_API_KEY": "shell-gemini",
                    "HF_TOKEN": "shell-hf",
                    "HUGGINGFACE_API_KEY": "shell-hf",
                },
                clear=True,
            ),
        ):
            handler._start_proxy()

        self.assertNotIn("OPENAI_API_KEY", captured_env)
        self.assertNotIn("GEMINI_API_KEY", captured_env)
        self.assertNotIn("HF_TOKEN", captured_env)
        self.assertNotIn("HUGGINGFACE_API_KEY", captured_env)
        self.assertIn("Qwen local", handler.state.message)


if __name__ == "__main__":
    unittest.main()
