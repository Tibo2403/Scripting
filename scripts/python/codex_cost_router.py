"""Optional cost-routing wrapper for Codex CLI and a self-hosted LiteLLM OSS proxy."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_TEMPLATE = SCRIPT_DIR / "plugins" / "litellm_cost_router.toml"
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
CODEX_CONFIG = CODEX_HOME / "config.toml"
CODEX_PLUGIN = CODEX_HOME / "plugins" / "litellm_cost_router.toml"
LOG_DIR = CODEX_HOME / "logs"
LOG_FILE = LOG_DIR / "cost_router.jsonl"
STATE_FILE = LOG_DIR / "cost_router_state.json"
CONFIG_BACKUP = LOG_DIR / "config.toml.cost_router_backup"
BEGIN_MARKER = "# BEGIN CODEX COST ROUTER"
END_MARKER = "# END CODEX COST ROUTER"
DEFAULT_MAX_INPUT_TOKENS = 12_000
DEFAULT_MAX_OUTPUT_TOKENS = 2_000
MODELS = ("codex-cheap", "codex-auto", "codex-strong")
LITELLM_HOST = "localhost"
LITELLM_PORT = 4000
WINDOWS_LITELLM_FALLBACK = Path(r"C:\tmp\litellm-oss\Scripts\litellm.exe")

# Approximate placeholders in USD per million tokens. Adjust these estimates to
# match the deployments configured in your local LiteLLM OSS proxy.
ESTIMATED_RATES = {
    "codex-cheap": {"input": 0.15, "output": 0.60},
    "codex-auto": {"input": 0.50, "output": 2.00},
    "codex-strong": {"input": 2.00, "output": 8.00},
}

SIMPLE_TERMS = (
    "correction mineure",
    "résumé",
    "resume",
    "documentation",
    "petite modification",
    "typo",
    "readme",
)
MEDIUM_TERMS = (
    "refactor",
    "test",
    "docker",
    "api",
    "python",
    "typescript",
)
COMPLEX_TERMS = (
    "sécurité",
    "securite",
    "security",
    "fiscalité",
    "fiscalite",
    "odoo",
    "architecture",
    "migration",
    "production",
    "rls",
    "supabase",
    "bug critique",
    "critical bug",
)

PROFILE_BLOCK = """\
# BEGIN CODEX COST ROUTER
[model_providers.litellm]
name = "LiteLLM OSS Cost Router"
base_url = "http://localhost:4000/v1"
env_key = "LITELLM_API_KEY"
wire_api = "responses"

[profiles.cost-routing]
model = "codex-auto"
model_provider = "litellm"
model_reasoning_effort = "low"
# END CODEX COST ROUTER
"""


def utc_now() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def ensure_directories() -> None:
    """Create Codex directories used by this optional tool."""
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    CODEX_PLUGIN.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


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
        rf"\n?{re.escape(BEGIN_MARKER)}.*?{re.escape(END_MARKER)}\n?",
        flags=re.DOTALL,
    )
    return pattern.sub("\n", config).rstrip() + ("\n" if config.strip() else "")


def load_state() -> dict[str, Any]:
    """Load local router state without failing on a damaged state file."""
    try:
        return json.loads(read_text(STATE_FILE)) if STATE_FILE.exists() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(**updates: Any) -> dict[str, Any]:
    """Merge and store local router state."""
    state = load_state()
    state.update(updates)
    write_text(STATE_FILE, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    return state


def append_log(record: dict[str, Any]) -> None:
    """Append a JSONL routing record without storing prompts or API keys."""
    ensure_directories()
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_history() -> list[dict[str, Any]]:
    """Read valid JSONL routing records."""
    records: list[dict[str, Any]] = []
    if not LOG_FILE.exists():
        return records
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def clean_text(text: str) -> str:
    """Remove HTML, long comments, duplicate lines, and unnecessary whitespace."""
    text = re.sub(r"(?is)<script.*?>.*?</script>|<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)/\*.{500,}?\*/", "/* long comment removed */", text)
    text = re.sub(r"(?m)^\s*(#|//).{500,}$", r"\1 long comment removed", text)
    text = re.sub(r"<[^>]+>", " ", text)

    result: list[str] = []
    previous = ""
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            if result and result[-1] != "":
                result.append("")
            continue
        if line == previous:
            continue
        result.append(line)
        previous = line
    return "\n".join(result).strip()


def compress_logs(text: str) -> str:
    """Collapse repetitive logs and remove noisy low-value lines."""
    lines = text.splitlines()
    result: list[str] = []
    counts: dict[str, int] = {}
    noise = re.compile(
        r"(?i)\b(debug|trace|verbose|progress|downloaded|transformed|rendering chunks)\b"
    )
    for line in lines:
        normalized = re.sub(r"\d+", "<n>", line.strip())
        if noise.search(line) and not re.search(r"(?i)\b(error|fail|warning|exception)\b", line):
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
        if counts[normalized] <= 2:
            result.append(line)
        elif counts[normalized] == 3:
            result.append(f"[repeated log lines omitted: {normalized}]")
    return "\n".join(result)


def estimate_tokens(text: str) -> int:
    """Estimate tokens conservatively without requiring a tokenizer package."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def smart_truncate(text: str, max_tokens: int) -> str:
    """Keep the beginning and end of oversized context with a clear marker."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    marker = "\n\n[... context truncated by codex_cost_router ...]\n\n"
    remaining = max(0, max_chars - len(marker))
    head = int(remaining * 0.70)
    tail = remaining - head
    return text[:head].rstrip() + marker + text[-tail:].lstrip()


def classify_complexity(prompt: str) -> tuple[str, str]:
    """Classify a task using explicit, explainable keyword rules."""
    normalized = prompt.casefold()
    complex_matches = [term for term in COMPLEX_TERMS if term in normalized]
    medium_matches = [term for term in MEDIUM_TERMS if term in normalized]
    simple_matches = [term for term in SIMPLE_TERMS if term in normalized]

    if complex_matches:
        return "complex", f"complex keyword: {', '.join(complex_matches[:3])}"
    if medium_matches or estimate_tokens(prompt) > 1_500:
        detail = ", ".join(medium_matches[:3]) or "large prompt"
        return "medium", f"medium complexity: {detail}"
    if simple_matches:
        return "simple", f"simple task: {', '.join(simple_matches[:3])}"
    return "medium", "default routing for an unclassified task"


def route_model(prompt: str, force_model: str | None = None) -> tuple[str, str]:
    """Choose a LiteLLM model alias."""
    if force_model:
        return force_model, "model forced by CLI option"
    complexity, reason = classify_complexity(prompt)
    model = {
        "simple": "codex-cheap",
        "medium": "codex-auto",
        "complex": "codex-strong",
    }[complexity]
    return model, reason


def build_optimized_prompt(prompt: str, max_input_tokens: int) -> str:
    """Apply context cleanup, log compression, and intelligent truncation."""
    return smart_truncate(clean_text(compress_logs(prompt)), max_input_tokens)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate request cost from editable placeholder deployment rates."""
    rates = ESTIMATED_RATES[model]
    return round(
        (input_tokens / 1_000_000) * rates["input"]
        + (output_tokens / 1_000_000) * rates["output"],
        8,
    )


def enable_router() -> int:
    """Install the optional profile while preserving all existing Codex settings."""
    ensure_directories()
    if not PLUGIN_TEMPLATE.exists():
        raise FileNotFoundError(f"Missing plugin template: {PLUGIN_TEMPLATE}")
    shutil.copyfile(PLUGIN_TEMPLATE, CODEX_PLUGIN)

    config = read_text(CODEX_CONFIG)
    if BEGIN_MARKER not in config and CODEX_CONFIG.exists():
        shutil.copyfile(CODEX_CONFIG, CONFIG_BACKUP)
    config = remove_profile_block(config)
    updated = config.rstrip() + ("\n\n" if config.strip() else "") + PROFILE_BLOCK
    write_text(CODEX_CONFIG, updated)
    save_state(enabled=True, enabled_at=utc_now(), current_model="codex-auto")
    print("Cost routing enabled.")
    print("LiteLLM OSS profile installed: cost-routing")
    print("Start the profile with:")
    print("  codex --profile cost-routing")
    print("Use optimized one-shot routing with:")
    print('  python codex_cost_router.py run "your task"')
    return 0


def disable_router() -> int:
    """Remove only the installed profile and plugin fragment."""
    ensure_directories()
    if CONFIG_BACKUP.exists():
        shutil.copyfile(CONFIG_BACKUP, CODEX_CONFIG)
        CONFIG_BACKUP.unlink()
    else:
        write_text(CODEX_CONFIG, remove_profile_block(read_text(CODEX_CONFIG)))
    if CODEX_PLUGIN.exists():
        CODEX_PLUGIN.unlink()
    save_state(enabled=False, disabled_at=utc_now())
    print("Cost routing disabled. Existing Codex configuration was preserved.")
    return 0


def router_enabled() -> bool:
    """Check that both managed config markers and plugin fragment exist."""
    config = read_text(CODEX_CONFIG)
    return BEGIN_MARKER in config and END_MARKER in config and CODEX_PLUGIN.exists()


def print_status() -> int:
    """Display router state and the latest routing decision."""
    state = load_state()
    history = read_history()
    latest = history[-1] if history else {}
    print("Codex Cost Router")
    print("-----------------")
    print(f"Plugin active      : {'yes' if router_enabled() else 'no'}")
    print(f"Current model      : {latest.get('model', state.get('current_model', 'codex-auto'))}")
    print(f"Last estimated cost: ${latest.get('estimated_cost_usd', 0):.8f}")
    print(f"Last routing       : {latest.get('routing_reason', 'none')}")
    print(f"Execution mode     : {latest.get('execution_mode', 'none')}")
    return 0


def print_history(limit: int) -> int:
    """Display recent routing records as a compact table."""
    records = read_history()[-limit:]
    print("Timestamp                  Model          Input  Output  Ratio   Estimated USD")
    print("-------------------------  -------------  -----  ------  ------  -------------")
    for item in records:
        print(
            f"{item.get('timestamp', '')[:25]:25}  "
            f"{item.get('model', ''):13}  "
            f"{item.get('estimated_input_tokens', 0):5}  "
            f"{item.get('estimated_output_tokens', 0):6}  "
            f"{item.get('compression_ratio', 0):6.2f}  "
            f"${item.get('estimated_cost_usd', 0):.8f}"
        )
    return 0


def print_stats() -> int:
    """Display aggregate estimated routing statistics."""
    records = read_history()
    if not records:
        print("No routing history yet.")
        return 0
    total_cost = sum(float(item.get("estimated_cost_usd", 0)) for item in records)
    total_savings = sum(float(item.get("estimated_savings_usd", 0)) for item in records)
    original = sum(int(item.get("original_input_tokens", 0)) for item in records)
    optimized = sum(int(item.get("estimated_input_tokens", 0)) for item in records)
    print("Codex Cost Router statistics")
    print("----------------------------")
    print(f"Requests routed          : {len(records)}")
    print(f"Original input tokens    : {original}")
    print(f"Optimized input tokens   : {optimized}")
    print(f"Tokens removed           : {max(0, original - optimized)}")
    print(f"Estimated routed cost    : ${total_cost:.8f}")
    print(f"Estimated savings vs strong: ${total_savings:.8f}")
    print()
    return print_history(10)


def find_codex() -> str | None:
    """Locate Codex CLI without assuming a specific Windows installation path."""
    return shutil.which("codex") or os.environ.get("CODEX_CLI_PATH")


def find_litellm() -> str | None:
    """Locate LiteLLM CLI, including the documented short-path Windows venv."""
    configured = os.environ.get("LITELLM_CLI_PATH")
    if configured and Path(configured).is_file():
        return configured
    discovered = shutil.which("litellm")
    if discovered:
        return discovered
    if WINDOWS_LITELLM_FALLBACK.is_file():
        return str(WINDOWS_LITELLM_FALLBACK)
    return None


def proxy_available() -> bool:
    """Check whether the local LiteLLM OSS proxy is accepting TCP connections."""
    try:
        with socket.create_connection((LITELLM_HOST, LITELLM_PORT), timeout=1):
            return True
    except OSError:
        return False


def print_doctor() -> int:
    """Display local setup checks without printing secret values."""
    checks = [
        ("Codex CLI", bool(find_codex()), find_codex() or "not found"),
        ("LiteLLM command", bool(find_litellm()), find_litellm() or "not found"),
        ("LiteLLM proxy localhost:4000", proxy_available(), "listening" if proxy_available() else "not listening"),
        ("LITELLM_API_KEY", bool(os.environ.get("LITELLM_API_KEY")), "set" if os.environ.get("LITELLM_API_KEY") else "missing"),
        ("OPENAI_API_KEY", bool(os.environ.get("OPENAI_API_KEY")), "set" if os.environ.get("OPENAI_API_KEY") else "missing"),
        ("PYTHONUTF8", os.environ.get("PYTHONUTF8") == "1", "1" if os.environ.get("PYTHONUTF8") == "1" else "missing or not 1"),
        ("Cost-routing profile", router_enabled(), "enabled" if router_enabled() else "disabled"),
    ]
    print("Codex Cost Router doctor")
    print("------------------------")
    for name, passed, detail in checks:
        print(f"{'OK' if passed else 'FIX':3}  {name:30} {detail}")
    if not proxy_available():
        print("\nStart LiteLLM OSS with:")
        executable = find_litellm() or "litellm"
        print(f"  & '{executable}' --config .\\scripts\\python\\litellm-cost-routing.yaml --port 4000")
    return 0 if all(passed for _, passed, _ in checks) else 1


def run_router(args: argparse.Namespace) -> int:
    """Optimize, log, and optionally execute a one-shot Codex CLI request."""
    prompt = " ".join(args.prompt).strip()
    optimized = build_optimized_prompt(prompt, args.max_input_tokens)
    model, reason = route_model(prompt, args.force_model)
    original_tokens = estimate_tokens(prompt)
    input_tokens = estimate_tokens(optimized)
    output_tokens = args.max_output_tokens
    compression_ratio = round(input_tokens / max(1, original_tokens), 4)
    cost = estimate_cost(model, input_tokens, output_tokens)
    strong_cost = estimate_cost("codex-strong", input_tokens, output_tokens)
    execution_mode = "dry-run" if args.dry_run else "codex-exec"

    record = {
        "timestamp": utc_now(),
        "model": model,
        "original_input_tokens": original_tokens,
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "compression_ratio": compression_ratio,
        "routing_reason": reason,
        "execution_mode": execution_mode,
        "estimated_cost_usd": cost,
        "estimated_savings_usd": round(max(0.0, strong_cost - cost), 8),
    }
    append_log(record)
    save_state(current_model=model, last_routing=record)

    print(f"Model             : {model}")
    print(f"Routing reason    : {reason}")
    print(f"Input tokens      : {original_tokens} -> {input_tokens}")
    print(f"Compression ratio : {compression_ratio:.2f}")
    print(f"Output budget     : {output_tokens}")
    print(f"Estimated cost    : ${cost:.8f}")

    if args.dry_run:
        print("\nOptimized prompt:")
        print(optimized)
        return 0

    if not router_enabled():
        print("Cost routing is disabled. Run: python codex_cost_router.py enable", file=sys.stderr)
        return 2
    if not proxy_available():
        print("LiteLLM OSS proxy is not listening on http://localhost:4000.", file=sys.stderr)
        print("Run: python codex_cost_router.py doctor", file=sys.stderr)
        return 4
    codex = find_codex()
    if not codex:
        print("Codex CLI was not found in PATH or CODEX_CLI_PATH.", file=sys.stderr)
        return 3

    command = [
        codex,
        "exec",
        "--profile",
        "cost-routing",
        "--model",
        model,
        *args.codex_arg,
        optimized,
    ]
    return subprocess.run(command, check=False).returncode


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("enable", help="Install the optional Codex profile.")
    subparsers.add_parser("disable", help="Remove the optional Codex profile.")
    subparsers.add_parser("status", help="Show activation and latest routing status.")
    subparsers.add_parser("doctor", help="Check Codex, LiteLLM, keys, proxy, and profile.")
    subparsers.add_parser("stats", help="Show aggregate estimated savings.")

    history = subparsers.add_parser("history", help="Show recent routing history.")
    history.add_argument("--limit", type=int, default=10)

    run = subparsers.add_parser("run", help="Optimize a prompt and call Codex CLI.")
    run.add_argument("prompt", nargs="+", help="Prompt sent to Codex after optimization.")
    run.add_argument("--dry-run", action="store_true", help="Show routing without calling Codex.")
    run.add_argument("--force-model", choices=MODELS)
    run.add_argument("--max-input-tokens", type=int, default=DEFAULT_MAX_INPUT_TOKENS)
    run.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    run.add_argument(
        "--codex-arg",
        action="append",
        default=[],
        help="Additional Codex exec argument. Repeat once per argument.",
    )
    return parser


def normalize_legacy_flags(argv: list[str]) -> list[str]:
    """Accept the requested --enable, --disable, and --status convenience flags."""
    aliases = {"--enable": "enable", "--disable": "disable", "--status": "status"}
    if argv and argv[0] in aliases:
        return [aliases[argv[0]], *argv[1:]]
    return argv


def main(argv: list[str] | None = None) -> int:
    """Run the selected router command."""
    args = build_parser().parse_args(normalize_legacy_flags(argv or sys.argv[1:]))
    if args.command == "enable":
        return enable_router()
    if args.command == "disable":
        return disable_router()
    if args.command == "status":
        return print_status()
    if args.command == "stats":
        return print_stats()
    if args.command == "doctor":
        return print_doctor()
    if args.command == "history":
        return print_history(args.limit)
    return run_router(args)


if __name__ == "__main__":
    raise SystemExit(main())
