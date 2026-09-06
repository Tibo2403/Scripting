"""Validate the security invariants of the Akash documentation agent."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
PINNED_IMAGE = re.compile(
    r"(?:ARG\s+\w+_IMAGE|image:)[^\n]*:[^\s@]+@sha256:[0-9a-f]{64}(?:\s|$)"
)


def require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def validate(root: Path = ROOT, repository_root: Path = REPOSITORY_ROOT) -> list[str]:
    """Return all static security and deployment invariant violations."""
    errors: list[str] = []
    try:
        config = load_json(root / "config" / "openclaw.json")
        deploy = (root / "deploy.yaml").read_text(encoding="utf-8")
        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        ollama_dockerfile = (root / "Dockerfile.ollama").read_text(encoding="utf-8")
        workflow = (
            repository_root / ".github" / "workflows" / "akash-openclaw-doc-agent.yml"
        ).read_text(encoding="utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        return [f"Unable to load deployment inputs: {error}"]

    try:
        require(
            errors,
            config["gateway"]["bind"] == "loopback",
            "Gateway must bind to loopback.",
        )
        require(
            errors,
            config["gateway"]["auth"]["mode"] == "token",
            "Gateway token auth is required.",
        )
        require(
            errors,
            config["tools"]["elevated"]["enabled"] is False,
            "Elevated tools must be disabled.",
        )

        allowed = set(config["tools"]["allow"])
        denied = set(config["tools"]["deny"])
    except (KeyError, TypeError, ValueError) as error:
        return [f"Invalid OpenClaw configuration structure: missing or invalid {error}."]

    require(
        errors,
        allowed == {"read", "write", "edit", "apply_patch"},
        "Unexpected allowed tool.",
    )
    require(
        errors,
        {"exec", "process", "browser", "sessions_spawn"} <= denied,
        "Dangerous tool not denied.",
    )

    require(
        errors,
        "USER node" in dockerfile,
        "Agent image must run as the node user.",
    )
    require(
        errors,
        "USER agent" in ollama_dockerfile,
        "Ollama image must run as the agent user.",
    )
    require(
        errors,
        len(PINNED_IMAGE.findall(dockerfile + ollama_dockerfile)) == 2,
        "Both base images must be pinned by tag and sha256 digest.",
    )
    require(
        errors,
        deploy.count("__AGENT_IMAGE__") == 1
        and deploy.count("__OLLAMA_IMAGE__") == 1,
        "SDL must remain a fail-closed template with exactly two image placeholders.",
    )
    require(
        errors,
        ":latest" not in dockerfile + ollama_dockerfile + deploy,
        "latest tags are forbidden.",
    )
    require(
        errors,
        "OPENCLAW_GATEWAY_TOKEN=" not in deploy,
        "Gateway token must not be committed.",
    )
    require(
        errors,
        "OPENCLAW_EXECUTABLE=" not in deploy,
        "The production OpenClaw executable cannot be overridden.",
    )
    require(
        errors,
        "port: 18789" not in deploy,
        "Gateway port must not be exposed in the SDL.",
    )
    require(
        errors,
        re.search(r"port:\s*8080[\s\S]{0,100}global:\s*true", deploy) is not None,
        "Only the health endpoint should be global.",
    )
    require(
        errors,
        re.search(r"port:\s*11434[\s\S]{0,100}service:\s*agent", deploy) is not None,
        "Ollama must stay private.",
    )
    ollama_exposure = ""
    if "port: 11434" in deploy:
        ollama_exposure = deploy.split("port: 11434", maxsplit=1)[1].split(
            "\n\nprofiles:", maxsplit=1
        )[0]
    require(
        errors,
        "global: true" not in ollama_exposure,
        "Ollama cannot have a global endpoint.",
    )
    require(
        errors,
        "mount: /workspace" in deploy
        and "name: workspace" in deploy
        and "persistent: true" in deploy,
        "Workspace must use named persistent Akash storage.",
    )
    require(
        errors,
        "mount: /home/agent/.ollama/models" in deploy
        and "name: ollama-models" in deploy,
        "Ollama models must use named persistent Akash storage.",
    )
    require(
        errors,
        "actions/checkout@" in workflow,
        "Workflow checkout action is missing.",
    )
    require(
        errors,
        "actions/checkout@v" not in workflow,
        "Workflow actions must be SHA-pinned.",
    )
    require(
        errors,
        "python -m unittest discover" in workflow,
        "Validator regression tests must run in CI.",
    )
    require(errors, "node --test" in workflow, "Agent runtime tests must run in CI.")
    require(
        errors,
        "tests/test-run-ollama.sh" in workflow,
        "Ollama runtime tests must run in CI.",
    )
    require(
        errors,
        workflow.count("docker build --check") == 2,
        "Both Docker build definitions must be checked in CI.",
    )
    require(
        errors,
        "scripts/render_deploy.py" in workflow
        and "deploy.resolved.yaml" in workflow,
        "Publish workflow must render an immutable deployment artifact.",
    )
    require(
        errors,
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
        in workflow,
        "Deployment artifact upload must be SHA-pinned.",
    )
    require(
        errors,
        "provider-services tx deployment" not in workflow.lower()
        and "akash tx deployment" not in workflow.lower(),
        "Workflow must not deploy Akash.",
    )
    return errors


def main() -> int:
    errors = validate()

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Akash OpenClaw security validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
