"""Codex cost router: admin responsibilities."""

from __future__ import annotations
import os
import shutil

import codex_router_availability as router_availability
import codex_router_config as router_config
import codex_router_storage as router_storage


def enable_router() -> int:
    """Install the optional profile while preserving all existing Codex settings."""
    router_storage.ensure_directories()
    config = router_storage.read_text(router_config.CODEX_CONFIG)
    if router_config.BEGIN_MARKER not in config and router_config.CODEX_CONFIG.exists():
        shutil.copyfile(router_config.CODEX_CONFIG, router_config.CONFIG_BACKUP)
    config = router_storage.remove_profile_block(config)
    router_storage.write_text(router_config.CODEX_CONFIG, config)
    router_storage.write_text(
        router_config.COST_ROUTING_CONFIG, router_config.COST_ROUTING_PROFILE
    )
    router_storage.write_text(
        router_config.COST_ROUTING_HF_CONFIG, router_config.COST_ROUTING_HF_PROFILE
    )
    router_storage.save_state(
        enabled=True,
        enabled_at=router_storage.utc_now(),
        current_model=router_config.DEFAULT_MODEL,
    )
    print("Cost routing enabled.")
    print("LiteLLM OSS profile installed: cost-routing")
    print("Optional Hugging Face profile installed: cost-routing-hf")
    print("Start the profile with:")
    print("  codex --profile cost-routing")
    print("  codex --profile cost-routing-hf")
    print("Use optimized one-shot routing with:")
    print('  python codex_cost_router.py run "your task"')
    return 0


def disable_router() -> int:
    """Remove only the installed profile and plugin fragment."""
    router_storage.ensure_directories()
    if router_config.CONFIG_BACKUP.exists():
        shutil.copyfile(router_config.CONFIG_BACKUP, router_config.CODEX_CONFIG)
        router_config.CONFIG_BACKUP.unlink()
    else:
        router_storage.write_text(
            router_config.CODEX_CONFIG,
            router_storage.remove_profile_block(
                router_storage.read_text(router_config.CODEX_CONFIG)
            ),
        )
    router_config.COST_ROUTING_CONFIG.unlink(missing_ok=True)
    router_config.COST_ROUTING_HF_CONFIG.unlink(missing_ok=True)
    router_storage.save_state(enabled=False, disabled_at=router_storage.utc_now())
    print("Cost routing disabled. Existing Codex configuration was preserved.")
    return 0


def router_enabled() -> bool:
    """Check that both managed profile markers exist."""
    return router_config.COST_ROUTING_CONFIG.exists()


def print_status() -> int:
    """Display router state and the latest routing decision."""
    state = router_storage.load_state()
    history = router_storage.read_history()
    latest = history[-1] if history else {}
    print("Codex Cost Router")
    print("-----------------")
    print(f"Profile active     : {'yes' if router_enabled() else 'no'}")
    print(
        f"Current model      : {latest.get('model', state.get('current_model', router_config.DEFAULT_MODEL))}"
    )
    print(f"Codex profile      : {latest.get('codex_profile', 'none')}")
    print(f"Last estimated cost: ${latest.get('estimated_cost_usd', 0):.8f}")
    print(f"Last routing       : {latest.get('routing_reason', 'none')}")
    print(f"Execution mode     : {latest.get('execution_mode', 'none')}")
    return 0


def print_history(limit: int, *, business_only: bool = False) -> int:
    """Display recent routing records as a compact table."""
    records = router_storage.read_history()
    if business_only:
        records = [item for item in records if router_storage.is_business_record(item)]
    records = records[-limit:]
    print(
        "Timestamp                  Model          Input  Output  Ratio   Estimated USD"
    )
    print(
        "-------------------------  -------------  -----  ------  ------  -------------"
    )
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
    records = router_storage.read_history()
    business_records = [
        item for item in records if router_storage.is_business_record(item)
    ]
    if not business_records:
        print("No completed business executions yet (dry-runs are excluded).")
        return 0
    total_cost = sum(
        float(item.get("estimated_cost_usd", 0)) for item in business_records
    )
    total_savings = sum(
        float(item.get("estimated_savings_usd", 0)) for item in business_records
    )
    original = sum(
        int(item.get("original_input_tokens", 0)) for item in business_records
    )
    optimized = sum(
        int(item.get("estimated_input_tokens", 0)) for item in business_records
    )
    print("Codex Cost Router statistics")
    print("----------------------------")
    print(f"Completed executions     : {len(business_records)}")
    print(
        f"Dry-runs excluded        : {sum(item.get('execution_mode') == 'dry-run' for item in records)}"
    )
    print(f"Original input tokens    : {original}")
    print(f"Optimized input tokens   : {optimized}")
    print(f"Tokens removed           : {max(0, original - optimized)}")
    print(f"Estimated routed cost    : ${total_cost:.8f}")
    adaptive_records = [
        item
        for item in business_records
        if isinstance(item.get("adaptive_router"), dict)
    ]
    switches = sum(
        1 for item in adaptive_records if item["adaptive_router"].get("would_switch")
    )
    applied = sum(
        1 for item in adaptive_records if item["adaptive_router"].get("applied")
    )
    print(f"Estimated savings vs strong: ${total_savings:.8f}")
    if adaptive_records:
        print(f"Adaptive observations   : {len(adaptive_records)}")
        print(f"Adaptive would switch   : {switches}")
        print(f"Adaptive applied switch : {applied}")
    print()
    return print_history(10, business_only=True)


def print_doctor() -> int:
    """Display local setup checks without printing secret values."""
    checks = [
        (
            "Codex CLI",
            bool(router_availability.find_codex()),
            router_availability.find_codex() or "not found",
        ),
        ("Standard Codex path", True, "default work path; no proxy required"),
        (
            "LiteLLM command optional",
            True,
            router_availability.find_litellm() or "not found; proxy dispatch disabled",
        ),
        (
            "LiteLLM proxy optional",
            True,
            "listening for Gemini/Phi/Qwen/Claude aliases"
            if router_availability.proxy_available()
            else "inactive; standard Codex remains usable",
        ),
        (
            "Gemini dispatch optional",
            True,
            "ready through proxy"
            if router_availability.proxy_available()
            and os.environ.get("GEMINI_API_KEY")
            else "needs active proxy + GEMINI_API_KEY",
        ),
        (
            "Ollama Phi small-task optional",
            True,
            "listening; small tasks can use Phi-4 Mini"
            if router_availability.phi_available()
            else "missing; run ollama pull phi4-mini and start Ollama",
        ),
        (
            "Ollama Qwen optional",
            True,
            "listening on 127.0.0.1:11434"
            if router_availability.qwen_available()
            else "missing; run Start-CodexQwenOllama.ps1",
        ),
        (
            "Claude complex optional",
            True,
            "ready through proxy"
            if router_availability.proxy_available()
            and router_availability.claude_available()
            else "needs active proxy + ANTHROPIC_API_KEY",
        ),
        (
            "HF_TOKEN optional",
            True,
            "set"
            if router_availability.hf_available()
            else "missing; Hugging Face aliases disabled",
        ),
        (
            "PYTHONUTF8 optional",
            True,
            "1" if os.environ.get("PYTHONUTF8") == "1" else "not forced",
        ),
        (
            "Cost-routing profile optional",
            True,
            "enabled" if router_enabled() else "disabled",
        ),
    ]
    print("Codex Cost Router doctor")
    print("------------------------")
    for name, passed, detail in checks:
        print(f"{'OK' if passed else 'FIX':3}  {name:30} {detail}")
    if not router_availability.proxy_available():
        print(
            "\nLiteLLM is optional. Start it only when you want Gemini/Claude/API dispatch:"
        )
        executable = router_availability.find_litellm() or "litellm"
        print(
            f"  & '{executable}' --config .\\scripts\\python\\litellm-cost-routing.yaml --port 4000"
        )
    return 0 if all(passed for _, passed, _ in checks) else 1
