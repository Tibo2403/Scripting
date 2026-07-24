"""Validate the security invariants of the Akash documentation agent."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
ERRORS: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


def main() -> int:
    config = json.loads((ROOT / "config" / "openclaw.json").read_text(encoding="utf-8"))
    deploy = (ROOT / "deploy.yaml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ollama_dockerfile = (ROOT / "Dockerfile.ollama").read_text(encoding="utf-8")
    workflow = (
        REPOSITORY_ROOT / ".github" / "workflows" / "akash-openclaw-doc-agent.yml"
    ).read_text(encoding="utf-8")

    require(config["gateway"]["bind"] == "loopback", "Gateway must bind to loopback.")
    require(config["gateway"]["auth"]["mode"] == "token", "Gateway token auth is required.")
    require(config["tools"]["elevated"]["enabled"] is False, "Elevated tools must be disabled.")

    allowed = set(config["tools"]["allow"])
    denied = set(config["tools"]["deny"])
    require(allowed == {"read", "write", "edit", "apply_patch"}, "Unexpected allowed tool.")
    require({"exec", "process", "browser", "sessions_spawn"} <= denied, "Dangerous tool not denied.")

    require("USER node" in dockerfile, "Agent image must run as the node user.")
    require("USER agent" in ollama_dockerfile, "Ollama image must run as the agent user.")
    require(":latest" not in dockerfile + ollama_dockerfile + deploy, "latest tags are forbidden.")
    require("OPENCLAW_GATEWAY_TOKEN=" not in deploy, "Gateway token must not be committed.")
    require("port: 18789" not in deploy, "Gateway port must not be exposed in the SDL.")
    require(
        re.search(r"port:\s*8080[\s\S]{0,100}global:\s*true", deploy) is not None,
        "Only the health endpoint should be global.",
    )
    require(
        re.search(r"port:\s*11434[\s\S]{0,100}service:\s*agent", deploy) is not None,
        "Ollama must stay private.",
    )
    ollama_exposure = deploy.split("port: 11434", maxsplit=1)[1].split(
        "\n\nprofiles:", maxsplit=1
    )[0]
    require("global: true" not in ollama_exposure, "Ollama cannot have a global endpoint.")
    require("actions/checkout@" in workflow, "Workflow checkout action is missing.")
    require("actions/checkout@v" not in workflow, "Workflow actions must be SHA-pinned.")
    require("akash" not in workflow.lower().split("docker push")[-1], "Workflow must not deploy Akash.")

    if ERRORS:
        for error in ERRORS:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Akash OpenClaw security validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
