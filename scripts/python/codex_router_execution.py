"""Execution telemetry and category-aware business rewards for the AI router."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from queue import Queue
from typing import Sequence, TextIO


@dataclass(frozen=True)
class ExecutionResult:
    """Observed metrics for one completed execution attempt."""

    returncode: int
    latency_ms: int
    ttft_ms: int | None = None
    generated_tokens: int | None = None
    tokens_per_second: float | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.error

    def to_record(self) -> dict[str, object]:
        values = asdict(self)
        values["success"] = self.success
        return values


CATEGORY_REWARD_WEIGHTS = {
    "simple": {"quality": 0.15, "success": 0.25, "latency": 0.35, "cost": 0.25},
    "medium": {"quality": 0.30, "success": 0.30, "latency": 0.20, "cost": 0.20},
    "complex": {"quality": 0.45, "success": 0.35, "latency": 0.15, "cost": 0.05},
}


def business_reward(
    category: str,
    *,
    success: bool,
    latency_ms: int,
    cost_usd: float,
    quality_score: float | None = None,
) -> float:
    """Score observed utility, renormalizing when no quality judge is available."""
    weights = CATEGORY_REWARD_WEIGHTS.get(category, CATEGORY_REWARD_WEIGHTS["medium"])
    latency_target = {"simple": 2_000, "medium": 8_000, "complex": 25_000}.get(category, 8_000)
    cost_target = {"simple": 0.005, "medium": 0.05, "complex": 0.20}.get(category, 0.05)
    scores: dict[str, float] = {
        "success": 1.0 if success else 0.0,
        "latency": 1.0 / (1.0 + max(0, latency_ms) / latency_target),
        "cost": 1.0 / (1.0 + max(0.0, cost_usd) / cost_target),
    }
    if quality_score is not None:
        scores["quality"] = min(1.0, max(0.0, quality_score))
    available_weight = sum(weights[name] for name in scores)
    return round(sum(scores[name] * weights[name] for name in scores) / available_weight, 4)


def _pump(stream: TextIO, target: TextIO, channel: str, queue: Queue[tuple[str, str, float]]) -> None:
    for line in iter(stream.readline, ""):
        target.write(line)
        target.flush()
        queue.put((channel, line, time.perf_counter()))
    stream.close()


def run_streamed_command(command: Sequence[str]) -> ExecutionResult:
    """Run a command, preserve live output, and measure first useful stdout."""
    started = time.perf_counter()
    try:
        process = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        return ExecutionResult(6, 0, error=str(exc))
    if process.stdout is None or process.stderr is None:
        process.kill()
        return ExecutionResult(6, 0, error="unable to capture subprocess output")

    events: Queue[tuple[str, str, float]] = Queue()
    stdout_parts: list[str] = []
    threads = (
        threading.Thread(target=_pump, args=(process.stdout, sys.stdout, "stdout", events), daemon=True),
        threading.Thread(target=_pump, args=(process.stderr, sys.stderr, "stderr", events), daemon=True),
    )
    for thread in threads:
        thread.start()
    returncode = process.wait()
    for thread in threads:
        thread.join()

    first_output_at: float | None = None
    while not events.empty():
        channel, line, observed_at = events.get()
        if channel == "stdout":
            stdout_parts.append(line)
            if first_output_at is None and line.strip():
                first_output_at = observed_at
    finished = time.perf_counter()
    latency_ms = round((finished - started) * 1_000)
    ttft_ms = round((first_output_at - started) * 1_000) if first_output_at else None
    generated_tokens = max(1, (len("".join(stdout_parts)) + 3) // 4) if stdout_parts else 0
    generation_seconds = max((finished - (first_output_at or started)), 0.001)
    throughput = round(generated_tokens / generation_seconds, 3) if generated_tokens else None
    return ExecutionResult(returncode, latency_ms, ttft_ms, generated_tokens, throughput)
