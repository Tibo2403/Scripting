"""Tests for the optional Codex cost-routing wrapper."""

import importlib
import os
import shutil
import json
import argparse
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "codex_cost_router.py"
if str(MODULE_PATH.parent) not in sys.path:
    sys.path.insert(0, str(MODULE_PATH.parent))
ROUTER = importlib.import_module("codex_cost_router")
router_admin = importlib.import_module("codex_router_admin")
router_availability = importlib.import_module("codex_router_availability")
router_config = importlib.import_module("codex_router_config")
router_policy = importlib.import_module("codex_router_policy")
router_storage = importlib.import_module("codex_router_storage")


class CodexRouterIntegrationTests(unittest.TestCase):
    def test_run_router_dry_run_keeps_direct_codex_when_proxy_is_available(
        self,
    ) -> None:
        policy = {
            **router_config.DEFAULT_POLICY,
            "task_provider_rules": {"medium": "auto"},
            "fallback_order": ["litellm", "standard", "huggingface"],
        }
        args = argparse.Namespace(
            prompt=["Refactor this Python API"],
            max_input_tokens=router_config.DEFAULT_MAX_INPUT_TOKENS,
            policy=Path("unused-policy.yaml"),
            codex_provider=None,
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
                patch.object(router_availability, "proxy_available", return_value=True),
                patch.object(router_availability, "qwen_available", return_value=False),
                patch.object(router_availability, "phi_available", return_value=False),
            ):
                self.assertEqual(ROUTER.run_router(args), 0)
            record = json.loads(log_file.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(record["requested_codex_provider"], "litellm")
        self.assertEqual(record["codex_provider"], "standard")
        self.assertEqual(record["fallback_order"][0], "standard")

    def test_live_run_is_persisted_only_with_execution_metrics(self) -> None:
        policy = {
            **router_config.DEFAULT_POLICY,
            "task_provider_rules": {"medium": "auto"},
            "fallback_order": ["standard"],
        }
        args = argparse.Namespace(
            prompt=["Refactor this Python API"],
            max_input_tokens=router_config.DEFAULT_MAX_INPUT_TOKENS,
            policy=Path("unused-policy.yaml"),
            codex_provider="standard",
            provider="openai",
            force_model=None,
            max_output_tokens=router_config.DEFAULT_MAX_OUTPUT_TOKENS,
            dry_run=False,
            codex_arg=[],
        )
        result = ROUTER.ExecutionResult(0, 1_250, 180, 42, 39.7)
        with tempfile.TemporaryDirectory() as directory:
            log_file = Path(directory) / "cost_router.jsonl"
            state_file = Path(directory) / "cost_router_state.json"
            with (
                patch.object(router_config, "LOG_DIR", Path(directory)),
                patch.object(router_config, "LOG_FILE", log_file),
                patch.object(router_config, "STATE_FILE", state_file),
                patch.object(router_policy, "load_policy", return_value=policy),
                patch.object(router_availability, "find_codex", return_value="codex"),
                patch.object(
                    router_availability, "proxy_available", return_value=False
                ),
                patch.object(router_availability, "phi_available", return_value=False),
                patch.object(router_availability, "qwen_available", return_value=False),
                patch.object(ROUTER, "run_streamed_command", return_value=result),
            ):
                self.assertEqual(ROUTER.run_router(args), 0)
            record = json.loads(log_file.read_text(encoding="utf-8").splitlines()[0])
        self.assertTrue(record["success"])
        self.assertEqual(record["returncode"], 0)
        self.assertEqual(record["latency_ms"], 1_250)
        self.assertEqual(record["ttft_ms"], 180)
        self.assertEqual(record["generated_tokens"], 42)
        self.assertEqual(record["tokens_per_second"], 39.7)
        self.assertEqual(record["prompt_category"], "medium")
        self.assertIn("business_reward", record)

    def test_stats_exclude_dry_runs_from_business_kpis(self) -> None:
        history = [
            {"execution_mode": "dry-run", "estimated_cost_usd": 99.0},
            {
                "execution_mode": "codex-exec",
                "success": True,
                "returncode": 0,
                "estimated_cost_usd": 0.01,
                "estimated_savings_usd": 0.02,
            },
        ]
        with (
            patch.object(router_storage, "read_history", return_value=history),
            patch("sys.stdout", new_callable=StringIO) as output,
        ):
            self.assertEqual(router_admin.print_stats(), 0)
        rendered = output.getvalue()
        self.assertIn("Completed executions     : 1", rendered)
        self.assertIn("Dry-runs excluded        : 1", rendered)
        self.assertIn("$0.01000000", rendered)
        self.assertNotIn("99.00000000", rendered)

    def test_remove_profile_block_preserves_unrelated_configuration(self) -> None:
        config = "[features]\njs_repl = false\n\n" + router_config.PROFILE_BLOCK
        self.assertEqual(
            router_storage.remove_profile_block(config),
            "[features]\njs_repl = false\n",
        )

    def test_find_litellm_uses_configured_existing_path(self) -> None:
        with tempfile.NamedTemporaryFile() as executable:
            with patch.dict(os.environ, {"LITELLM_CLI_PATH": executable.name}):
                self.assertEqual(router_availability.find_litellm(), executable.name)

    def test_find_codex_prefers_configured_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            executable = home / "codex.exe"
            executable.write_text("", encoding="utf-8")
            config = home / "config.toml"
            config.write_text(
                f"[mcp_servers.node_repl.env]\nCODEX_CLI_PATH = '{executable}'\n",
                encoding="utf-8",
            )
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(router_config, "CODEX_CONFIG", config),
                patch.object(shutil, "which", return_value="blocked-windowsapps-codex"),
            ):
                self.assertEqual(router_availability.find_codex(), str(executable))

    def test_enable_disable_restores_original_config_bytes(self) -> None:
        initial = b"[features]\r\njs_repl = false\r\n"
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config = home / "config.toml"
            config.write_bytes(initial)
            with (
                patch.object(router_config, "CODEX_HOME", home),
                patch.object(router_config, "CODEX_CONFIG", config),
                patch.object(router_config, "LOG_DIR", home / "logs"),
                patch.object(
                    router_config, "LOG_FILE", home / "logs" / "cost_router.jsonl"
                ),
                patch.object(
                    router_config,
                    "STATE_FILE",
                    home / "logs" / "cost_router_state.json",
                ),
                patch.object(
                    router_config,
                    "CONFIG_BACKUP",
                    home / "logs" / "config.toml.cost_router_backup",
                ),
                patch.object(
                    router_config,
                    "COST_ROUTING_CONFIG",
                    home / "cost-routing.config.toml",
                ),
                patch.object(
                    router_config,
                    "COST_ROUTING_HF_CONFIG",
                    home / "cost-routing-hf.config.toml",
                ),
            ):
                router_admin.enable_router()
                router_admin.disable_router()
            self.assertEqual(config.read_bytes(), initial)


if __name__ == "__main__":
    unittest.main()
