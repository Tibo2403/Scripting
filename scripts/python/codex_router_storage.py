"""Codex cost router: storage responsibilities."""

from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from codex_router_execution import ExecutionResult, business_reward

import codex_router_config as router_config


def utc_now() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def ensure_directories() -> None:
    """Create Codex directories used by this optional tool."""
    router_config.CODEX_HOME.mkdir(parents=True, exist_ok=True)
    router_config.LOG_DIR.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    """Read UTF-8 text when a file exists."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, content: str) -> None:
    """Write UTF-8 text after creating the parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def remove_profile_block(config: str) -> str:
    """Remove only the managed profile block from a Codex config file."""
    pattern = re.compile(
        rf"\n?{re.escape(router_config.BEGIN_MARKER)}.*?{re.escape(router_config.END_MARKER)}\n?",
        flags=re.DOTALL,
    )
    return pattern.sub("\n", config).rstrip() + ("\n" if config.strip() else "")


def load_state() -> dict[str, Any]:
    """Load local router state without failing on a damaged state file."""
    try:
        return (
            json.loads(read_text(router_config.STATE_FILE))
            if router_config.STATE_FILE.exists()
            else {}
        )
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(**updates: Any) -> dict[str, Any]:
    """Merge and store local router state."""
    state = load_state()
    state.update(updates)
    write_text(
        router_config.STATE_FILE, json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    )
    return state


def append_log(record: dict[str, Any]) -> None:
    """Append a JSONL routing record without storing prompts or API keys."""
    ensure_directories()
    with router_config.LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_history() -> list[dict[str, Any]]:
    """Read valid JSONL routing records."""
    records: list[dict[str, Any]] = []
    if not router_config.LOG_FILE.exists():
        return records
    for line in router_config.LOG_FILE.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def is_business_record(record: dict[str, Any]) -> bool:
    """Return whether a completed, non-dry-run observation may influence KPIs."""
    return record.get("execution_mode") != "dry-run" and (
        "success" in record or "returncode" in record
    )


def phi_throughput_guard_reason(records: list[dict[str, Any]]) -> str | None:
    """Open Phi's circuit when its latest measured throughput misses the floor."""
    for item in reversed(records):
        if (
            not is_business_record(item)
            or item.get("model") not in router_config.LOCAL_SMALL_MODELS
        ):
            continue
        try:
            throughput = float(item.get("tokens_per_second"))
        except (TypeError, ValueError):
            continue
        if throughput < router_config.SMALL_TASK_TARGET_TOKENS_PER_SECOND:
            return (
                f"last Phi throughput {throughput:.2f} tok/s is below "
                f"{router_config.SMALL_TASK_TARGET_TOKENS_PER_SECOND:.2f} tok/s"
            )
        return None
    return None


def finalize_execution_record(
    record: dict[str, Any],
    result: ExecutionResult,
    attempt_provider: str | None,
    attempt_model: str | None,
) -> None:
    """Persist a completed observation exactly once, after execution finishes."""
    record.update(result.to_record())
    record["attempt_provider"] = attempt_provider
    record["attempt_model"] = attempt_model
    record["kpi_eligible"] = True
    record["business_reward"] = business_reward(
        str(record.get("prompt_category") or "medium"),
        success=result.success,
        latency_ms=result.latency_ms,
        cost_usd=float(record.get("estimated_cost_usd") or 0.0),
        quality_score=None,
    )
    append_log(record)
    save_state(current_model=str(record["model"]), last_routing=record)
