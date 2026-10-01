"""Codex cost router: main responsibilities."""

from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path
from codex_prompt_classifier import classify_prompt
from codex_router_execution import ExecutionResult, run_streamed_command

import codex_router_adaptive as router_adaptive
import codex_router_admin as router_admin
import codex_router_availability as router_availability
import codex_router_config as router_config
import codex_router_ollama as router_ollama
import codex_router_policy as router_policy
import codex_router_prompt as router_prompt
import codex_router_providers as router_providers
import codex_router_selection as router_selection
import codex_router_storage as router_storage


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate request cost from editable placeholder deployment rates."""
    rates = router_config.ESTIMATED_RATES[model]
    return round(
        (input_tokens / 1_000_000) * rates["input"]
        + (output_tokens / 1_000_000) * rates["output"],
        8,
    )


def run_router(args: argparse.Namespace) -> int:
    """Optimize, log, and optionally execute a one-shot Codex CLI request."""
    prompt = " ".join(args.prompt).strip()
    prompt_classification = classify_prompt(prompt)
    optimized = router_prompt.build_optimized_prompt(prompt, args.max_input_tokens)
    policy = router_policy.load_policy(args.policy)
    selected_codex_provider, codex_provider_reason = (
        router_providers.codex_provider_from_policy(args.codex_provider, policy)
    )
    selected_provider, provider_reason = router_providers.provider_from_policy(
        prompt, args.provider, policy
    )
    effective_provider = (
        "huggingface"
        if selected_codex_provider == "huggingface" and selected_provider == "auto"
        else selected_provider
    )
    model, reason = router_selection.route_model(
        prompt, args.force_model, effective_provider
    )
    preserve_direct_traffic = router_providers.should_preserve_direct_traffic(
        args.codex_provider, policy
    )
    fallback_order = router_providers.traffic_preserving_fallback_order(
        selected_codex_provider,
        effective_provider,
        model,
        policy,
        preserve_direct_traffic,
    )
    adaptive_decision = router_adaptive.adaptive_router_decision(fallback_order, policy)
    fallback_order = router_providers.preserve_direct_traffic_order(
        list(adaptive_decision["effective_order"]),
        selected_codex_provider,
        effective_provider,
        model,
        preserve_direct_traffic,
    )
    active_codex_provider = (
        fallback_order[0] if fallback_order else selected_codex_provider
    )
    selected_codex_profile = router_providers.codex_profile(active_codex_provider)
    selected_codex_model = router_providers.codex_model(model, active_codex_provider)
    original_tokens = router_prompt.estimate_tokens(prompt)
    input_tokens = router_prompt.estimate_tokens(optimized)
    output_tokens = (
        min(args.max_output_tokens, router_config.SMALL_TASK_MAX_OUTPUT_TOKENS)
        if model in router_config.LOCAL_SMALL_MODELS
        else args.max_output_tokens
    )
    compression_ratio = round(input_tokens / max(1, original_tokens), 4)
    cost = estimate_cost(model, input_tokens, output_tokens)
    max_cost = float(policy.get("max_cost_usd") or 0)
    strong_cost = estimate_cost(
        router_config.DEFAULT_MODEL, input_tokens, output_tokens
    )
    execution_mode = "dry-run" if args.dry_run else "codex-exec"

    record = {
        "timestamp": router_storage.utc_now(),
        "model": model,
        "provider": effective_provider,
        "provider_reason": provider_reason,
        "codex_provider": active_codex_provider,
        "requested_codex_provider": selected_codex_provider,
        "codex_provider_reason": codex_provider_reason,
        "codex_profile": selected_codex_profile,
        "codex_model": selected_codex_model,
        "fallback_order": fallback_order,
        "adaptive_router": {
            "enabled": adaptive_decision["enabled"],
            "shadow_mode": adaptive_decision["shadow_mode"],
            "baseline_provider": adaptive_decision["baseline_provider"],
            "suggested_provider": adaptive_decision["suggested_provider"],
            "confidence_delta": adaptive_decision["confidence_delta"],
            "would_switch": adaptive_decision["would_switch"],
            "applied": adaptive_decision["applied"],
            "cost_guard_blocked": adaptive_decision["cost_guard_blocked"],
            "cost_multiplier": adaptive_decision["cost_multiplier"],
            "max_cost_multiplier": adaptive_decision["max_cost_multiplier"],
            "health": adaptive_decision["health"],
        },
        "original_input_tokens": original_tokens,
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "compression_ratio": compression_ratio,
        "routing_reason": reason,
        "prompt_category": prompt_classification.category,
        "prompt_risk_score": prompt_classification.risk_score,
        "prompt_semantic_score": prompt_classification.semantic_score,
        "classification_signals": list(prompt_classification.signals),
        "execution_mode": execution_mode,
        "estimated_cost_usd": cost,
        "policy_max_cost_usd": max_cost,
        "estimated_savings_usd": round(max(0.0, strong_cost - cost), 8),
    }
    print(f"Model             : {model}")
    print(f"Provider          : {effective_provider}")
    print(f"Codex profile     : {selected_codex_profile}")
    print(f"Codex model       : {selected_codex_model}")
    print(f"Fallback order    : {', '.join(fallback_order)}")
    if adaptive_decision["enabled"]:
        print(
            "Adaptive router   : "
            f"{'applied' if adaptive_decision['applied'] else 'shadow'} "
            f"{adaptive_decision['baseline_provider']} -> {adaptive_decision['suggested_provider']} "
            f"(delta={adaptive_decision['confidence_delta']:.2f})"
        )
        if adaptive_decision["cost_guard_blocked"]:
            print(
                "Cost guard        : blocked expensive switch "
                f"(x{adaptive_decision['cost_multiplier']:.2f} > "
                f"x{adaptive_decision['max_cost_multiplier']:.2f})"
            )
    print(f"Routing reason    : {reason}")
    print(f"Input tokens      : {original_tokens} -> {input_tokens}")
    print(f"Compression ratio : {compression_ratio:.2f}")
    print(f"Output budget     : {output_tokens}")
    print(f"Estimated cost    : ${cost:.8f}")
    print(
        f"Proxy active      : {'yes' if router_availability.proxy_available() else 'no'}"
    )
    print(
        f"Phi small local   : {'yes' if router_availability.phi_available() else 'no'}"
    )
    print(
        f"Qwen local        : {'yes' if router_availability.qwen_available() else 'no'}"
    )
    if model in router_config.LOCAL_SMALL_MODELS:
        print(
            "Small-task target : "
            f">= {router_config.SMALL_TASK_TARGET_TOKENS_PER_SECOND:.1f} tok/s with <= {router_config.SMALL_TASK_MAX_OUTPUT_TOKENS} output tokens"
        )
    if max_cost > 0 and cost > max_cost:
        print(f"Policy cost limit : ${max_cost:.8f} exceeded")

    if args.dry_run:
        record["kpi_eligible"] = False
        router_storage.append_log(record)
        router_storage.save_state(current_model=model, last_routing=record)
        print("\nOptimized prompt:")
        print(optimized)
        return 0

    codex = router_availability.find_codex()
    execution_started = time.perf_counter()
    last_returncode = 0
    last_result: ExecutionResult | None = None
    last_attempt_provider: str | None = None
    last_attempt_model: str | None = None
    for attempt_provider in fallback_order:
        ready, message = router_providers.codex_provider_ready(attempt_provider)
        if not ready:
            print(f"Skipping {attempt_provider}: {message}", file=sys.stderr)
            last_returncode = 5 if attempt_provider == "huggingface" else 4
            continue
        if attempt_provider != "standard" and not router_admin.router_enabled():
            print(
                f"Skipping {attempt_provider}: managed Codex profile is not enabled.",
                file=sys.stderr,
            )
            last_returncode = 4
            continue
        if (
            attempt_provider == "standard"
            and model in router_config.LOCAL_SMALL_MODELS
            and router_availability.phi_available()
        ):
            print(
                "Executing through local Ollama Phi-4 Mini (no LiteLLM proxy required)"
            )
            result = router_ollama.run_phi_local(optimized, output_tokens)
            router_storage.finalize_execution_record(
                record, result, attempt_provider, router_config.PHI_OLLAMA_MODEL
            )
            return result.returncode
        if (
            attempt_provider == "standard"
            and model == router_config.QWEN_LOCAL_MODEL
            and router_availability.qwen_available()
        ):
            print("Executing through local Ollama Qwen (no LiteLLM proxy required)")
            result = router_ollama.run_qwen_local(optimized, output_tokens)
            router_storage.finalize_execution_record(
                record, result, attempt_provider, router_config.QWEN_OLLAMA_MODEL
            )
            return result.returncode
        if not codex:
            message = "Codex CLI was not found in PATH or CODEX_CLI_PATH."
            print(message, file=sys.stderr)
            result = ExecutionResult(
                3,
                round((time.perf_counter() - execution_started) * 1_000),
                error=message,
            )
            router_storage.finalize_execution_record(
                record, result, attempt_provider, None
            )
            return result.returncode
        attempt_profile = router_providers.codex_profile(attempt_provider)
        attempt_model = router_providers.codex_model(model, attempt_provider)
        print(f"Executing through {attempt_profile} ({attempt_model})")
        command = router_providers.build_codex_command(
            codex,
            attempt_provider,
            model,
            args.codex_arg,
            optimized,
        )
        last_result = run_streamed_command(command)
        last_returncode = last_result.returncode
        last_attempt_provider = attempt_provider
        last_attempt_model = attempt_model
        if last_returncode == 0:
            router_storage.finalize_execution_record(
                record, last_result, attempt_provider, attempt_model
            )
            return last_returncode
        print(
            f"Provider {attempt_provider} failed with exit code {last_returncode}.",
            file=sys.stderr,
        )
    if last_result is None:
        last_result = ExecutionResult(
            last_returncode or 6,
            round((time.perf_counter() - execution_started) * 1_000),
            error="no provider was ready for execution",
        )
    router_storage.finalize_execution_record(
        record, last_result, last_attempt_provider, last_attempt_model
    )
    return last_result.returncode


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("enable", help="Install the optional Codex profile.")
    subparsers.add_parser("disable", help="Remove the optional Codex profile.")
    subparsers.add_parser("status", help="Show activation and latest routing status.")
    subparsers.add_parser(
        "doctor", help="Check Codex, LiteLLM, keys, proxy, and profile."
    )
    subparsers.add_parser("stats", help="Show aggregate estimated savings.")

    history = subparsers.add_parser("history", help="Show recent routing history.")
    history.add_argument("--limit", type=int, default=10)

    run = subparsers.add_parser("run", help="Optimize a prompt and call Codex CLI.")
    run.add_argument(
        "prompt", nargs="+", help="Prompt sent to Codex after optimization."
    )
    run.add_argument(
        "--dry-run", action="store_true", help="Show routing without calling Codex."
    )
    run.add_argument("--force-model", choices=router_config.MODELS)
    run.add_argument(
        "--policy",
        type=Path,
        default=router_config.POLICY_FILE,
        help="Routing policy YAML file.",
    )
    run.add_argument(
        "--provider",
        choices=router_config.PROVIDERS,
        default=None,
        help="Provider preference behind LiteLLM. Can also be set with CODEX_ROUTER_PROVIDER.",
    )
    run.add_argument(
        "--codex-provider",
        choices=router_config.CODEX_PROVIDERS,
        default=None,
        help=(
            "Codex-facing provider path: auto chooses LiteLLM when active, "
            "standard uses normal Codex, litellm uses the local proxy, and "
            "huggingface uses the optional direct HF layer."
        ),
    )
    run.add_argument(
        "--max-input-tokens", type=int, default=router_config.DEFAULT_MAX_INPUT_TOKENS
    )
    run.add_argument(
        "--max-output-tokens", type=int, default=router_config.DEFAULT_MAX_OUTPUT_TOKENS
    )
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
        return router_admin.enable_router()
    if args.command == "disable":
        return router_admin.disable_router()
    if args.command == "status":
        return router_admin.print_status()
    if args.command == "stats":
        return router_admin.print_stats()
    if args.command == "doctor":
        return router_admin.print_doctor()
    if args.command == "history":
        return router_admin.print_history(args.limit)
    return run_router(args)


if __name__ == "__main__":
    raise SystemExit(main())
