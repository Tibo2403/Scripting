"""HTTP forwarding and streaming lifecycle for the risk router."""

import json
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from typing import Any

import risk_router_core as core
from risk_router_config import UPSTREAM_BASE, RETRYABLE_STATUSES, STREAM_TOKEN_BYTES


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
            self.send_json(200, core.load_state())
            return
        if self.path == "/dispatch/metrics":
            self.send_json(200, core.summarize_state(core.load_state()))
            return
        self.proxy_request("GET", None)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if self.path == "/dispatch/reset":
            core.save_state({"models": {}, "requests": []})
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

    def route_order(self, payload: dict[str, Any]) -> tuple[str, str, list[core.Choice], list[str]]:
        requested = str(payload.get("model", "codex-default"))
        state = core.load_state()
        selected, choices = core.choose_model(state, requested)
        ordered = [selected] + [choice.model for choice in choices if choice.model != selected and not choice.hard_limited]
        if not choices:
            ordered = [selected]
        return requested, selected, choices, ordered[:3]

    def handle_json_chat(self, payload: dict[str, Any]) -> None:
        requested, selected, choices, ordered = self.route_order(payload)
        prompt_token_estimate = core.estimate_prompt_tokens(payload)

        last_body = b""
        last_status = 502
        last_headers: list[tuple[str, str]] = []
        attempts = []
        for candidate in ordered:
            payload["model"] = candidate
            queue_depth = core.acquire_in_flight(candidate)
            started = time.perf_counter()
            try:
                status, headers, body, error = self.forward_json("/v1/chat/completions", payload)
            finally:
                core.release_in_flight(candidate)
            elapsed_ms = (time.perf_counter() - started) * 1000
            ok = 200 <= status < 300
            response_tokens = core.extract_completion_tokens(body)
            generation_seconds = max(elapsed_ms / 1000.0, 0.001)
            tokens_per_second = response_tokens / generation_seconds if response_tokens else 0.0
            core.update_state(
                lambda state, candidate=candidate: core.update_metrics(
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

        self.record_request(requested, selected, attempts, choices)
        self.write_proxy_response(last_status, last_headers, last_body, requested, selected, attempts)

    def handle_streaming_chat(self, payload: dict[str, Any]) -> None:
        requested, selected, choices, ordered = self.route_order(payload)
        prompt_token_estimate = core.estimate_prompt_tokens(payload)
        attempts = []
        last_status = 502
        last_headers: list[tuple[str, str]] = []
        last_body = b""

        for candidate in ordered:
            payload["model"] = candidate
            queue_depth = core.acquire_in_flight(candidate)
            started = time.perf_counter()
            response = None
            try:
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
                    core.update_state(
                        lambda state, candidate=candidate: core.update_metrics(
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
                    self.record_request(requested, selected, attempts, choices)
                    self.write_proxy_response(last_status, last_headers, last_body, requested, selected, attempts)
                    return

                status = response.status
                last_headers = list(response.headers.items())
                self.send_response(status)
                for key, value in core.response_headers(last_headers):
                    self.send_header(key, value)
                self.send_header("X-Risk-Router-Requested-Model", requested)
                self.send_header("X-Risk-Router-Selected-Model", candidate)
                self.send_header("X-Risk-Router-Attempts", json.dumps(attempts, separators=(",", ":")))
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True

                first_ms = None
                streamed_bytes = 0
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
                core.update_state(
                    lambda state, candidate=candidate: core.update_metrics(
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
                self.record_request(requested, selected, attempts, choices)
                return
            finally:
                try:
                    if response is not None:
                        response.close()
                finally:
                    core.release_in_flight(candidate)

    def record_request(
        self,
        requested: str,
        selected: str,
        attempts: list[dict[str, Any]],
        choices: list[core.Choice],
    ) -> None:
        core.update_state(
            lambda state: core.append_request(
                state,
                {
                    "ts": core.now(),
                    "requested_model": requested,
                    "selected_model": selected,
                    "attempts": attempts,
                    "choices": [choice.__dict__ for choice in choices],
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
        for key, value in core.response_headers(headers):
            self.send_header(key, value)
        if requested:
            self.send_header("X-Risk-Router-Requested-Model", requested)
            self.send_header("X-Risk-Router-Selected-Model", selected)
            self.send_header("X-Risk-Router-Attempts", json.dumps(attempts, separators=(",", ":")))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
