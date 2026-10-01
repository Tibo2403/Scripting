"""Codex cost router: policy responsibilities."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

import codex_router_config as router_config
import codex_router_storage as router_storage


def _parse_scalar(value: str) -> Any:
    """Parse a tiny YAML scalar subset without requiring PyYAML."""
    value = value.strip().strip("'\"")
    lowered = value.casefold()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def parse_simple_policy(text: str) -> dict[str, Any]:
    """Parse the small policy YAML shape used by this router."""
    policy: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        line = raw_line.split("#", 1)[0].rstrip()
        if line.startswith("  - ") and current_key:
            policy.setdefault(current_key, []).append(_parse_scalar(line[4:]))
            continue
        if line.startswith("  ") and current_key:
            key, _, value = line.strip().partition(":")
            if key and value:
                policy.setdefault(current_key, {})[key.strip()] = _parse_scalar(value)
            continue
        key, _, value = line.partition(":")
        current_key = key.strip()
        policy[current_key] = (
            _parse_scalar(value)
            if value.strip()
            else ([] if current_key.endswith("_order") else {})
        )
    return policy


def load_policy(path: Path = router_config.POLICY_FILE) -> dict[str, Any]:
    """Load routing policy with defaults and no hard PyYAML dependency."""
    policy = json.loads(json.dumps(router_config.DEFAULT_POLICY))
    if not path.exists():
        return policy
    text = router_storage.read_text(path)
    try:
        import yaml  # type: ignore[import-untyped]

        loaded = yaml.safe_load(text) or {}
    except Exception:
        loaded = parse_simple_policy(text)
    if not isinstance(loaded, dict):
        return policy
    for key, value in loaded.items():
        if key in {"task_provider_rules", "adaptive_router"} and isinstance(
            value, dict
        ):
            policy[key].update(value)
        elif key in policy:
            policy[key] = value
    return policy
