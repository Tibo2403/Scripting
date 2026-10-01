"""Codex cost router: ollama responsibilities."""

from __future__ import annotations
import json
import sys
import time
import urllib.error
import urllib.request
from codex_router_execution import ExecutionResult

import codex_router_config as router_config
import codex_router_prompt as router_prompt


def run_ollama_local(
    prompt: str,
    max_output_tokens: int,
    ollama_model: str,
    label: str,
) -> ExecutionResult:
    """Stream a local Ollama response and return measured execution telemetry."""
    payload = {
        "model": ollama_model,
        "messages": [
            {"role": "system", "content": "You are a concise local coding assistant."},
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.1, "num_predict": max_output_tokens},
        "stream": True,
    }
    request = urllib.request.Request(
        router_config.OLLAMA_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    first_token_at: float | None = None
    completion_tokens = 0
    eval_duration_ns = 0
    output_parts: list[str] = []
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            for raw_line in response:
                if not raw_line.strip():
                    continue
                data = json.loads(raw_line.decode("utf-8"))
                content = str((data.get("message") or {}).get("content") or "")
                if content:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    output_parts.append(content)
                    print(content, end="", flush=True)
                if data.get("done"):
                    completion_tokens = int(data.get("eval_count") or 0)
                    eval_duration_ns = int(data.get("eval_duration") or 0)
    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        print(f"Local {label} call failed: {exc}", file=sys.stderr)
        latency_ms = round((time.perf_counter() - started) * 1_000)
        return ExecutionResult(7, latency_ms, error=str(exc))
    finished = time.perf_counter()
    latency_ms = round((finished - started) * 1_000)
    ttft_ms = round((first_token_at - started) * 1_000) if first_token_at else None
    if not completion_tokens and output_parts:
        completion_tokens = router_prompt.estimate_tokens("".join(output_parts))
    if eval_duration_ns > 0:
        throughput = completion_tokens / (eval_duration_ns / 1_000_000_000)
    elif completion_tokens and first_token_at:
        throughput = completion_tokens / max(finished - first_token_at, 0.001)
    else:
        throughput = None
    if output_parts:
        print()
    if completion_tokens:
        print(
            f"\n[local-{label}] completion_tokens={completion_tokens} "
            f"elapsed_s={(finished - started):.2f} tokens_per_s={(throughput or 0):.2f}"
        )
    return ExecutionResult(
        0,
        latency_ms,
        ttft_ms,
        completion_tokens,
        round(throughput, 3) if throughput is not None else None,
    )


def run_phi_local(prompt: str, max_output_tokens: int) -> ExecutionResult:
    """Call local Phi-4 Mini through Ollama without requiring the LiteLLM proxy."""
    return run_ollama_local(
        prompt, max_output_tokens, router_config.PHI_OLLAMA_MODEL, "phi"
    )


def run_qwen_local(prompt: str, max_output_tokens: int) -> ExecutionResult:
    """Call local Qwen through Ollama without requiring the LiteLLM proxy."""
    return run_ollama_local(
        prompt, max_output_tokens, router_config.QWEN_OLLAMA_MODEL, "qwen"
    )
