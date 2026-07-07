import json
import math
import random
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from adaptive_token_pressure_router import (
    choose_adaptive_route,
    estimate_prompt_tokens as estimate_pressure_tokens,
    markov_overload_risk,
    update_pressure_state,
)


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "risk-router-state.json"
UPSTREAM_BASE = "http://127.0.0.1:4000/v1"


ROUTE_CANDIDATES = {
    "codex-risk-adjusted": ["gemini-flash-direct", "gemini-pro-direct", "codex-qwen-local"],
    "codex-auto": ["gemini-flash-direct", "gemini-pro-direct", "codex-qwen-local"],
    "codex-light": ["gemini-flash-direct", "codex-qwen-local"],
    "codex-default": ["codex-qwen-local", "gemini-flash-direct", "gemini-pro-direct"],
    "codex-long": ["codex-qwen-local", "gemini-pro-direct"],
    "codex-deep": ["codex-qwen-local", "gemini-pro-direct"],
    "codex-no-openai": ["codex-qwen-local", "gemini-flash-direct", "gemini-pro-direct"],
    "codex-cheap": ["gemini-flash-direct", "codex-qwen-local"],
    "codex-strong": ["codex-qwen-local", "gemini-pro-direct"],
}


MODEL_PROFILE = {
    "gemini-flash-direct": {
        "cost": 0.20,
        "total_latency": 3500.0,
        "ttft": 900.0,
        "tokens_per_second": 45.0,
        "tpm_limit": 250_000,
        "rpm_limit": 60,
        "max_in_flight": 2,
    },
    "gemini-pro-direct": {
        "cost": 0.45,
        "total_latency": 6500.0,
        "ttft": 1600.0,
        "tokens_per_second": 28.0,
        "tpm_limit": 100_000,
        "rpm_limit": 30,
        "max_in_flight": 1,
    },
    "codex-qwen-local": {
        "cost": 0.02,
        "total_latency": 5500.0,
        "ttft": 1400.0,
        "tokens_per_second": 18.0,
        "tpm_limit": 1_000_000,
        "rpm_limit": 120,
        "max_in_flight": 1,
    },
    "codex-local-only": {
        "cost": 0.02,
        "total_latency": 5500.0,
        "ttft": 1400.0,
        "tokens_per_second": 18.0,
        "tpm_limit": 1_000_000,
        "rpm_limit": 120,
        "max_in_flight": 1,
    },
}


SOFT_WEIGHTS = {
    "cost": 0.10,
    "ttft": 0.22,
    "total_latency": 0.14,
    "tokens_per_second": 0.14,
    "error": 0.25,
    "token_pressure": 0.08,
    "queue": 0.07,
}
TEMPERATURE = 0.30
EWMA_ALPHA = 0.25
RETRYABLE_STATUSES = {404, 408, 409, 429, 500, 502, 503, 504}
HARD_LIMIT_STATUS_SECONDS = {
    401: 3600,
    403: 3600,
    404: 1800,
    429: 300,
}
STREAM_TOKEN_BYTES = 24
STATE_LOCK = threading.Lock()
IN_FLIGHT_LOCK = threading.Lock()
IN_FLIGHT: dict[str, int] = defaultdict(int)


@dataclass
class Choice:
    model: str
    risk: float
    probability: float
    hard_limited: bool = False
    hard_limit_reason: str | None = None
    in_flight: int = 0


def now() -> float:
    return time.time()


def load_state_unlocked() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"models": {}, "requests": []}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"models": {}, "requests": []}


def load_state() -> dict[str, Any]:
    with STATE_LOCK:
        return load_state_unlocked()


def save_state_unlocked(state: dict[str, Any]) -> None:
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE_PATH)


def save_state(state: dict[str, Any]) -> None:
    with STATE_LOCK:
        save_state_unlocked(state)


def update_state(mutator: Any) -> dict[str, Any]:
    with STATE_LOCK:
        state = load_state_unlocked()
        mutator(state)
        save_state_unlocked(state)
        return state


def profile_for(model: str) -> dict[str, float]:
    return MODEL_PROFILE.get(
        model,
        {
            "cost": 0.30,
            "total_latency": 6000.0,
            "ttft": 1500.0,
            "tokens_per_second": 25.0,
            "tpm_limit": 250_000,
            "rpm_limit": 60,
            "max_in_flight": 1,
        },
    )


def ensure_model_state(state: dict[str, Any], model: str) -> dict[str, Any]:
    models = state.setdefault("models", {})
    if model not in models:
        profile = profile_for(model)
        models[model] = {
            "ewma_cost": profile["cost"],
            "ewma_latency_ms": profile["total_latency"],
            "ewma_total_latency_ms": profile["total_latency"],
            "ewma_ttft_ms": profile["ttft"],
            "ewma_tokens_per_second": profile["tokens_per_second"],
            "ewma_queue_depth": 0.0,
            "ewma_error_rate": 0.0,
            "ewma_token_pressure": 0.0,
            "ewma_rpm_pressure": 0.0,
            "ewma_tpm": 0.0,
            "ewma_rpm": 0.0,
            "ewma_response_tokens": 0.0,
            "markov_overloaded": 0.0,
            "hard_limited_until": 0.0,
            "hard_limit_reason": None,
            "last_status": None,
            "last_error": None,
            "last_used_at": None,
            "calls": 0,
            "successes": 0,
            "failures": 0,
        }
    return models[model]


def ewma(old: float, sample: float) -> float:
    return (EWMA_ALPHA * sample) + ((1.0 - EWMA_ALPHA) * old)


def normalize(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    if math.isclose(lo, hi):
        return {key: 0.0 for key in values}
    return {key: (value - lo) / (hi - lo) for key, value in values.items()}


def get_in_flight(model: str) -> int:
    with IN_FLIGHT_LOCK:
        return int(IN_FLIGHT.get(model, 0))


def acquire_in_flight(model: str) -> int:
    with IN_FLIGHT_LOCK:
        current = int(IN_FLIGHT.get(model, 0))
        IN_FLIGHT[model] = current + 1
        return current


def release_in_flight(model: str) -> None:
    with IN_FLIGHT_LOCK:
        IN_FLIGHT[model] = max(0, int(IN_FLIGHT.get(model, 0)) - 1)


def hard_limit_for(state: dict[str, Any], model: str) -> str | None:
    metrics = ensure_model_state(state, model)
    until = float(metrics.get("hard_limited_until") or 0.0)
    if until > now():
        reason = str(metrics.get("hard_limit_reason") or "cooldown")
        return f"{reason}; {int(until - now())}s remaining"

    profile = profile_for(model)
    in_flight = get_in_flight(model)
    max_in_flight = int(profile.get("max_in_flight", 1))
    if in_flight >= max_in_flight:
        return f"in_flight {in_flight}/{max_in_flight}"
    return None


def soft_risks_for(state: dict[str, Any], candidates: list[str]) -> dict[str, float]:
    cost = {}
    ttft = {}
    total_latency = {}
    generation_slowness = {}
    errors = {}
    token_pressure = {}
    queue = {}
    for model in candidates:
        metrics = ensure_model_state(state, model)
        cost[model] = float(metrics["ewma_cost"])
        ttft[model] = float(metrics["ewma_ttft_ms"])
        total_latency[model] = float(metrics["ewma_total_latency_ms"])
        generation_slowness[model] = -max(0.01, float(metrics["ewma_tokens_per_second"]))
        errors[model] = float(metrics["ewma_error_rate"])
        token_pressure[model] = float(metrics["ewma_token_pressure"])
        queue[model] = max(float(metrics.get("ewma_queue_depth", 0.0)), float(get_in_flight(model)))

    n_cost = normalize(cost)
    n_ttft = normalize(ttft)
    n_total_latency = normalize(total_latency)
    n_generation_slowness = normalize(generation_slowness)
    n_queue = normalize(queue)
    out = {}
    for model in candidates:
        out[model] = (
            SOFT_WEIGHTS["cost"] * n_cost[model]
            + SOFT_WEIGHTS["ttft"] * n_ttft[model]
            + SOFT_WEIGHTS["total_latency"] * n_total_latency[model]
            + SOFT_WEIGHTS["tokens_per_second"] * n_generation_slowness[model]
            + SOFT_WEIGHTS["error"] * errors[model]
            + SOFT_WEIGHTS["token_pressure"] * token_pressure[model]
            + SOFT_WEIGHTS["queue"] * n_queue[model]
        )
    return out


def adaptive_metrics_for(state: dict[str, Any], candidates: list[str]) -> dict[str, dict[str, float]]:
    out = {}
    for model in candidates:
        profile = profile_for(model)
        metrics = ensure_model_state(state, model)
        out[model] = {
            **profile,
            **metrics,
            "in_flight": get_in_flight(model),
        }
    return out


def choose_model(
    state: dict[str, Any],
    requested_model: str,
    prompt_token_estimate: int,
    dry_run: bool = False,
) -> tuple[str, list[Choice], dict[str, Any]]:
    candidates = ROUTE_CANDIDATES.get(requested_model)
    if not candidates:
        return requested_model, [], {
            "dry_run": dry_run,
            "selected_model": requested_model,
            "scores": [],
            "reason": "direct-model",
        }

    hard_reasons = {model: hard_limit_for(state, model) for model in candidates}
    eligible = [model for model in candidates if not hard_reasons[model]]
    all_hard_limited = not eligible
    scoring_candidates = eligible if eligible else candidates
    risks = soft_risks_for(state, scoring_candidates)
    scores = {model: math.exp(-risk / max(TEMPERATURE, 0.01)) for model, risk in risks.items()}
    total = sum(scores.values()) or 1.0
    probabilities = {model: scores[model] / total for model in scoring_candidates}

    draw = random.random()
    cumulative = 0.0
    selected = scoring_candidates[-1]
    for model in scoring_candidates:
        cumulative += probabilities[model]
        if draw <= cumulative:
            selected = model
            break

    choices = []
    for model in candidates:
        hard_reason = hard_reasons[model]
        choices.append(
            Choice(
                model=model,
                risk=risks.get(model, 1_000_000.0),
                probability=probabilities.get(model, 0.0),
                hard_limited=bool(hard_reason) and not all_hard_limited,
                hard_limit_reason=hard_reason,
                in_flight=get_in_flight(model),
            )
        )
    choices.sort(key=lambda item: (item.hard_limited, item.risk))

    pressure_decision = choose_adaptive_route(
        scoring_candidates,
        adaptive_metrics_for(state, scoring_candidates),
        prompt_tokens=prompt_token_estimate,
        response_tokens=0,
        in_flight={model: get_in_flight(model) for model in scoring_candidates},
        dry_run=dry_run,
    )
    selected = str(pressure_decision.get("selected_model") or selected)
    return selected, choices, pressure_decision


def estimate_prompt_tokens(payload: dict[str, Any]) -> int:
    return estimate_pressure_tokens(payload)


def extract_completion_tokens(body: bytes) -> int:
    try:
        data = json.loads(body.decode("utf-8"))
        usage = data.get("usage") or {}
        if usage.get("completion_tokens") is not None:
            return max(0, int(usage["completion_tokens"]))
        choices = data.get("choices") or []
        text = ""
        for choice in choices:
            message = choice.get("message") or {}
            text += str(message.get("content") or "")
        return max(1, len(text) // 4) if text else 0
    except Exception:
        return 0


def update_metrics(
    state: dict[str, Any],
    model: str,
    ok: bool,
    status: int,
    total_latency_ms: float,
    ttft_ms: float,
    tokens_per_second: float,
    prompt_token_estimate: int,
    response_tokens: int,
    queue_depth: int,
    error: str | None,
) -> None:
    metrics = ensure_model_state(state, model)
    metrics["calls"] += 1
    metrics["successes"] += 1 if ok else 0
    metrics["failures"] += 0 if ok else 1
    metrics["last_status"] = status
    metrics["last_error"] = error
    metrics["last_used_at"] = now()
    metrics["ewma_latency_ms"] = ewma(float(metrics["ewma_latency_ms"]), total_latency_ms)
    metrics["ewma_total_latency_ms"] = ewma(float(metrics["ewma_total_latency_ms"]), total_latency_ms)
    metrics["ewma_ttft_ms"] = ewma(float(metrics["ewma_ttft_ms"]), ttft_ms)
    metrics["ewma_queue_depth"] = ewma(float(metrics.get("ewma_queue_depth", 0.0)), float(queue_depth))
    metrics["ewma_error_rate"] = ewma(float(metrics["ewma_error_rate"]), 0.0 if ok else 1.0)
    if ok and tokens_per_second > 0:
        metrics["ewma_tokens_per_second"] = ewma(
            float(metrics["ewma_tokens_per_second"]),
            tokens_per_second,
        )
    if ok and response_tokens > 0:
        metrics["ewma_response_tokens"] = ewma(float(metrics.get("ewma_response_tokens", 0.0)), response_tokens)

    update_pressure_state(
        metrics,
        prompt_tokens=prompt_token_estimate,
        response_tokens=response_tokens,
        status=status,
        queue_depth=queue_depth,
    )
    metrics["markov_overloaded"] = markov_overload_risk(metrics)

    if status in HARD_LIMIT_STATUS_SECONDS:
        metrics["hard_limited_until"] = now() + HARD_LIMIT_STATUS_SECONDS[status]
        metrics["hard_limit_reason"] = f"http_{status}"
    elif ok:
        metrics["hard_limited_until"] = 0.0
        metrics["hard_limit_reason"] = None


def append_request(state: dict[str, Any], event: dict[str, Any]) -> None:
    requests = state.setdefault("requests", [])
    requests.append(event)
    del requests[:-200]


def response_headers(headers: list[tuple[str, str]]) -> list[tuple[str, str]]:
    blocked = {"transfer-encoding", "connection", "content-encoding", "content-length"}
    return [(key, value) for key, value in headers if key.lower() not in blocked]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def send_json(self, code: int, body: Any) -> None:
        data = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path in {"/health/readiness", "/health"}:
            self.send_json(200, {"status": "healthy", "router": "risk-adjusted"})
            return
        if self.path == "/dispatch/state":
            self.send_json(200, load_state())
            return
        if self.path == "/dispatch/metrics":
            self.send_json(200, summarize_state(load_state()))
            return
        self.proxy_request("GET", None)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if self.path == "/dispatch/reset":
            save_state({"models": {}, "requests": []})
            self.send_json(200, {"status": "reset"})
            return
        if self.path != "/v1/chat/completions":
            self.proxy_request("POST", raw)
            return

        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            self.send_json(400, {"error": f"invalid JSON body: {exc}"})
            return

        if payload.get("stream") is True:
            self.handle_streaming_chat(payload)
            return
        self.handle_json_chat(payload)

    def route_order(self, payload: dict[str, Any]) -> tuple[str, str, list[Choice], list[str], dict[str, Any], int]:
        requested = str(payload.get("model", "codex-default"))
        prompt_token_estimate = estimate_prompt_tokens(payload)
        dry_run = bool(payload.get("dry_run"))
        state = load_state()
        selected, choices, pressure_decision = choose_model(state, requested, prompt_token_estimate, dry_run=dry_run)
        ordered = [selected] + [choice.model for choice in choices if choice.model != selected and not choice.hard_limited]
        if not choices:
            ordered = [selected]
        return requested, selected, choices, ordered[:3], pressure_decision, prompt_token_estimate

    def handle_json_chat(self, payload: dict[str, Any]) -> None:
        requested, selected, choices, ordered, pressure_decision, prompt_token_estimate = self.route_order(payload)
        if payload.get("dry_run") is True:
            self.record_request(requested, selected, [], choices, pressure_decision)
            self.send_json(
                200,
                {
                    "dry_run": True,
                    "requested_model": requested,
                    "selected_model": selected,
                    "route_order": ordered,
                    "prompt_token_estimate": prompt_token_estimate,
                    "adaptive_token_pressure": pressure_decision,
                },
            )
            return

        last_body = b""
        last_status = 502
        last_headers: list[tuple[str, str]] = []
        attempts = []
        for candidate in ordered:
            payload["model"] = candidate
            queue_depth = acquire_in_flight(candidate)
            started = time.perf_counter()
            try:
                status, headers, body, error = self.forward_json("/v1/chat/completions", payload)
            finally:
                release_in_flight(candidate)
            elapsed_ms = (time.perf_counter() - started) * 1000
            ok = 200 <= status < 300
            response_tokens = extract_completion_tokens(body)
            generation_seconds = max(elapsed_ms / 1000.0, 0.001)
            tokens_per_second = response_tokens / generation_seconds if response_tokens else 0.0
            update_state(
                lambda state, candidate=candidate: update_metrics(
                    state,
                    candidate,
                    ok,
                    status,
                    elapsed_ms,
                    elapsed_ms,
                    tokens_per_second,
                    prompt_token_estimate,
                    response_tokens,
                    queue_depth,
                    error,
                )
            )
            attempts.append(
                {
                    "model": candidate,
                    "status": status,
                    "ok": ok,
                    "ms": round(elapsed_ms, 2),
                    "ttft_ms": round(elapsed_ms, 2),
                    "tokens_per_second": round(tokens_per_second, 2),
                    "queue_depth": queue_depth,
                }
            )
            if ok or candidate == ordered[-1] or status not in RETRYABLE_STATUSES:
                last_body = body
                last_status = status
                last_headers = headers
                break
            last_body = body
            last_status = status
            last_headers = headers

        self.record_request(requested, selected, attempts, choices, pressure_decision)
        self.write_proxy_response(last_status, last_headers, last_body, requested, selected, attempts)

    def handle_streaming_chat(self, payload: dict[str, Any]) -> None:
        requested, selected, choices, ordered, pressure_decision, prompt_token_estimate = self.route_order(payload)
        attempts = []
        last_status = 502
        last_headers: list[tuple[str, str]] = []
        last_body = b""

        for candidate in ordered:
            payload["model"] = candidate
            queue_depth = acquire_in_flight(candidate)
            started = time.perf_counter()
            response = None
            error = None
            try:
                response = self.open_stream("/v1/chat/completions", payload)
            except urllib.error.HTTPError as exc:
                last_status = exc.code
                last_headers = list(exc.headers.items())
                last_body = exc.read()
                error = last_body.decode("utf-8", errors="replace")[:1000]
            except Exception as exc:
                last_status = 502
                last_headers = []
                last_body = json.dumps({"error": str(exc)}).encode("utf-8")
                error = str(exc)

            if response is None:
                elapsed_ms = (time.perf_counter() - started) * 1000
                update_state(
                    lambda state, candidate=candidate: update_metrics(
                        state,
                        candidate,
                        False,
                        last_status,
                        elapsed_ms,
                        elapsed_ms,
                        0.0,
                        prompt_token_estimate,
                        0,
                        queue_depth,
                        error,
                    )
                )
                release_in_flight(candidate)
                attempts.append(
                    {
                        "model": candidate,
                        "status": last_status,
                        "ok": False,
                        "ms": round(elapsed_ms, 2),
                        "ttft_ms": round(elapsed_ms, 2),
                        "tokens_per_second": 0.0,
                        "queue_depth": queue_depth,
                    }
                )
                if candidate != ordered[-1] and last_status in RETRYABLE_STATUSES:
                    continue
                self.record_request(requested, selected, attempts, choices, pressure_decision)
                self.write_proxy_response(last_status, last_headers, last_body, requested, selected, attempts)
                return

            status = response.status
            last_headers = list(response.headers.items())
            self.send_response(status)
            for key, value in response_headers(last_headers):
                self.send_header(key, value)
            self.send_header("X-Risk-Router-Requested-Model", requested)
            self.send_header("X-Risk-Router-Selected-Model", candidate)
            self.send_header("X-Risk-Router-Attempts", json.dumps(attempts, separators=(",", ":")))
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

            first_ms = None
            streamed_bytes = 0
            try:
                while True:
                    chunk = response.read(4096)
                    if not chunk:
                        break
                    if first_ms is None and chunk.strip():
                        first_ms = (time.perf_counter() - started) * 1000
                    streamed_bytes += len(chunk)
                    self.wfile.write(chunk)
                    self.wfile.flush()
                total_ms = (time.perf_counter() - started) * 1000
                ttft_ms = first_ms if first_ms is not None else total_ms
                response_tokens = max(1, streamed_bytes // STREAM_TOKEN_BYTES) if streamed_bytes else 0
                generation_seconds = max((total_ms - ttft_ms) / 1000.0, total_ms / 1000.0, 0.001)
                tokens_per_second = response_tokens / generation_seconds if response_tokens else 0.0
                attempts.append(
                    {
                        "model": candidate,
                        "status": status,
                        "ok": 200 <= status < 300,
                        "ms": round(total_ms, 2),
                        "ttft_ms": round(ttft_ms, 2),
                        "tokens_per_second": round(tokens_per_second, 2),
                        "queue_depth": queue_depth,
                    }
                )
                update_state(
                    lambda state, candidate=candidate: update_metrics(
                        state,
                        candidate,
                        200 <= status < 300,
                        status,
                        total_ms,
                        ttft_ms,
                        tokens_per_second,
                        prompt_token_estimate,
                        response_tokens,
                        queue_depth,
                        None,
                    )
                )
                self.record_request(requested, selected, attempts, choices, pressure_decision)
                return
            finally:
                response.close()
                release_in_flight(candidate)

    def record_request(
        self,
        requested: str,
        selected: str,
        attempts: list[dict[str, Any]],
        choices: list[Choice],
        pressure_decision: dict[str, Any] | None = None,
    ) -> None:
        update_state(
            lambda state: append_request(
                state,
                {
                    "ts": now(),
                    "requested_model": requested,
                    "selected_model": selected,
                    "attempts": attempts,
                    "choices": [choice.__dict__ for choice in choices],
                    "adaptive_token_pressure": pressure_decision or {},
                },
            )
        )

    def proxy_request(self, method: str, body: bytes | None) -> None:
        target = UPSTREAM_BASE + self.path[3:] if self.path.startswith("/v1/") else "http://127.0.0.1:4000" + self.path
        headers = {key: value for key, value in self.headers.items() if key.lower() not in {"host", "content-length"}}
        request = urllib.request.Request(target, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                data = response.read()
                self.write_proxy_response(response.status, list(response.headers.items()), data, "", "", [])
        except urllib.error.HTTPError as exc:
            self.write_proxy_response(exc.code, list(exc.headers.items()), exc.read(), "", "", [])
        except Exception as exc:
            self.send_json(502, {"error": str(exc)})

    def forward_json(self, path: str, payload: dict[str, Any]) -> tuple[int, list[tuple[str, str]], bytes, str | None]:
        target = UPSTREAM_BASE + path[3:]
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.headers.get("Authorization", "Bearer local-dev"),
        }
        request = urllib.request.Request(target, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                return response.status, list(response.headers.items()), response.read(), None
        except urllib.error.HTTPError as exc:
            body = exc.read()
            return exc.code, list(exc.headers.items()), body, body.decode("utf-8", errors="replace")[:1000]
        except Exception as exc:
            return 502, [], json.dumps({"error": str(exc)}).encode("utf-8"), str(exc)

    def open_stream(self, path: str, payload: dict[str, Any]) -> Any:
        target = UPSTREAM_BASE + path[3:]
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.headers.get("Authorization", "Bearer local-dev"),
        }
        request = urllib.request.Request(target, data=data, headers=headers, method="POST")
        return urllib.request.urlopen(request, timeout=240)

    def write_proxy_response(
        self,
        status: int,
        headers: list[tuple[str, str]],
        body: bytes,
        requested: str,
        selected: str,
        attempts: list[dict[str, Any]],
    ) -> None:
        self.send_response(status)
        for key, value in response_headers(headers):
            self.send_header(key, value)
        if requested:
            self.send_header("X-Risk-Router-Requested-Model", requested)
            self.send_header("X-Risk-Router-Selected-Model", selected)
            self.send_header("X-Risk-Router-Attempts", json.dumps(attempts, separators=(",", ":")))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    models = state.get("models", {})
    summary = {}
    for model, metrics in models.items():
        calls = int(metrics.get("calls", 0))
        hard_limited_until = float(metrics.get("hard_limited_until") or 0.0)
        summary[model] = {
            "calls": calls,
            "success_rate": round(float(metrics.get("successes", 0)) / calls, 4) if calls else None,
            "ewma_ttft_ms": round(float(metrics.get("ewma_ttft_ms", 0)), 2),
            "ewma_total_latency_ms": round(float(metrics.get("ewma_total_latency_ms", 0)), 2),
            "ewma_latency_ms": round(float(metrics.get("ewma_latency_ms", 0)), 2),
            "ewma_tokens_per_second": round(float(metrics.get("ewma_tokens_per_second", 0)), 2),
            "ewma_queue_depth": round(float(metrics.get("ewma_queue_depth", 0)), 2),
            "in_flight": get_in_flight(model),
            "ewma_error_rate": round(float(metrics.get("ewma_error_rate", 0)), 4),
            "ewma_token_pressure": round(float(metrics.get("ewma_token_pressure", 0)), 4),
            "ewma_rpm_pressure": round(float(metrics.get("ewma_rpm_pressure", 0)), 4),
            "ewma_tpm": round(float(metrics.get("ewma_tpm", 0)), 2),
            "ewma_rpm": round(float(metrics.get("ewma_rpm", 0)), 2),
            "markov_overloaded": round(float(metrics.get("markov_overloaded", 0)), 4),
            "ewma_response_tokens": round(float(metrics.get("ewma_response_tokens", 0)), 2),
            "hard_limited": hard_limited_until > now(),
            "hard_limited_remaining_s": max(0, int(hard_limited_until - now())),
            "hard_limit_reason": metrics.get("hard_limit_reason"),
            "last_status": metrics.get("last_status"),
            "last_error": metrics.get("last_error"),
        }
    return {
        "strategy": "hard-limits + adaptive token pressure score",
        "soft_score_weights": SOFT_WEIGHTS,
        "temperature": TEMPERATURE,
        "hard_limits": {
            "status_cooldowns_seconds": HARD_LIMIT_STATUS_SECONDS,
            "max_in_flight": {model: int(profile["max_in_flight"]) for model, profile in MODEL_PROFILE.items()},
        },
        "models": summary,
    }


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 4001), Handler)
    print("Risk-adjusted router listening on http://127.0.0.1:4001")
    server.serve_forever()


if __name__ == "__main__":
    main()
