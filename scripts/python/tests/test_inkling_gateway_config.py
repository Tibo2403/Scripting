"""Static contract tests for the Codespaces Inkling gateway."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEVCONTAINER_ROOT = REPOSITORY_ROOT / ".devcontainer"
ROUTING_CONFIG = REPOSITORY_ROOT / "scripts" / "python" / "litellm-cost-routing.yaml"


class InklingGatewayConfigTests(unittest.TestCase):
    """Verify routing, authentication, and Codespaces exposure defaults."""

    def test_litellm_routes_only_to_the_official_inkling_endpoint(self) -> None:
        config = yaml.safe_load(
            (DEVCONTAINER_ROOT / "litellm-inkling.yaml").read_text(encoding="utf-8")
        )

        self.assertEqual(len(config["model_list"]), 1)
        route = config["model_list"][0]
        self.assertEqual(route["model_name"], "inkling")
        self.assertEqual(
            route["litellm_params"],
            {
                "model": "openai/thinkingmachines/inkling",
                "api_base": "https://ai-gateway.vercel.sh/v1",
                "api_key": "os.environ/INKLING_API_KEY",
            },
        )
        self.assertEqual(
            config["general_settings"]["master_key"],
            "os.environ/LITELLM_MASTER_KEY",
        )
        self.assertTrue(config["general_settings"]["disable_spend_logs"])

    def test_shared_router_uses_the_same_official_inkling_route(self) -> None:
        config = yaml.safe_load(ROUTING_CONFIG.read_text(encoding="utf-8"))
        routes = [
            route for route in config["model_list"] if route["model_name"] == "codex-inkling"
        ]

        self.assertEqual(len(routes), 1)
        params = routes[0]["litellm_params"]
        self.assertEqual(params["model"], "openai/thinkingmachines/inkling")
        self.assertEqual(params["api_base"], "https://ai-gateway.vercel.sh/v1")
        self.assertEqual(params["api_key"], "os.environ/INKLING_API_KEY")

    def test_codespaces_port_is_private_and_startup_is_idempotent(self) -> None:
        devcontainer = json.loads(
            (DEVCONTAINER_ROOT / "devcontainer.json").read_text(encoding="utf-8")
        )

        self.assertEqual(devcontainer["portsAttributes"]["4000"]["visibility"], "private")
        self.assertIn("--allow-missing-secrets", devcontainer["postStartCommand"])

        startup = (DEVCONTAINER_ROOT / "start-inkling-gateway.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("kill -0", startup)
        self.assertIn("INKLING_API_KEY", startup)
        self.assertIn("LITELLM_MASTER_KEY", startup)

    def test_devcontainer_files_do_not_contain_secret_values(self) -> None:
        secret_assignment = re.compile(
            r"(?m)^\s*(?:INKLING_API_KEY|LITELLM_MASTER_KEY)\s*=\s*(?!os\.environ/|[<{])\S+"
        )
        for path in DEVCONTAINER_ROOT.iterdir():
            if path.is_file():
                self.assertIsNone(secret_assignment.search(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
