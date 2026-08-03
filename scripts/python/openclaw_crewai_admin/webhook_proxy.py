#!/usr/bin/env python3
"""Proxy minimal : expose uniquement Google Chat, jamais le tableau de bord."""

from __future__ import annotations

import http.client
import os
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = int(os.environ.get("WEBHOOK_PROXY_PORT", "8080"))
UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = 18789
MAX_BODY = int(os.environ.get("WEBHOOK_MAX_BODY_BYTES", "1048576"))
RATE_LIMIT = int(os.environ.get("WEBHOOK_RATE_LIMIT_PER_MINUTE", "120"))
WINDOW_SECONDS = 60
CLEANUP_INTERVAL_SECONDS = WINDOW_SECONDS

requests_by_ip: dict[str, deque[float]] = defaultdict(deque)
rate_lock = threading.Lock()
last_cleanup = 0.0


def rate_allowed(ip: str) -> bool:
    global last_cleanup

    now = time.monotonic()
    with rate_lock:
        if now - last_cleanup >= CLEANUP_INTERVAL_SECONDS:
            cutoff = now - WINDOW_SECONDS
            stale_ips = [
                tracked_ip
                for tracked_ip, timestamps in requests_by_ip.items()
                if not timestamps or timestamps[-1] < cutoff
            ]
            for tracked_ip in stale_ips:
                del requests_by_ip[tracked_ip]
            last_cleanup = now

        bucket = requests_by_ip[ip]
        while bucket and bucket[0] < now - WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT:
            return False
        bucket.append(now)
        return True


class Handler(BaseHTTPRequestHandler):
    server_version = "OpenClawWebhookProxy/1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"proxy {self.client_address[0]} {fmt % args}", flush=True)

    def send_plain(self, status: int, message: str) -> None:
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in ("/healthz", "/readyz"):
            self.send_plain(404, "not found")
            return
        upstream_path = self.path
        connection = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=3)
        try:
            connection.request("GET", upstream_path)
            response = connection.getresponse()
            response.read(MAX_BODY)
            if response.status == 200:
                self.send_plain(200, "ok")
            else:
                self.send_plain(503, "gateway not ready")
        except (OSError, http.client.HTTPException):
            self.send_plain(503, "gateway unavailable")
        finally:
            connection.close()

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/googlechat", "/googlechat/"):
            self.send_plain(404, "not found")
            return
        if not rate_allowed(self.client_address[0]):
            self.send_plain(429, "rate limit exceeded")
            return
        content_type = self.headers.get("Content-Type", "").lower()
        if not content_type.startswith("application/json"):
            self.send_plain(415, "application/json required")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_plain(400, "invalid content length")
            return
        if length <= 0 or length > MAX_BODY:
            self.send_plain(413, "invalid body size")
            return
        body = self.rfile.read(length)
        headers = {
            "Content-Type": self.headers["Content-Type"],
            "Content-Length": str(len(body)),
        }
        authorization = self.headers.get("Authorization")
        if authorization:
            headers["Authorization"] = authorization
        connection = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=15)
        try:
            connection.request("POST", "/googlechat", body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read(MAX_BODY)
            self.send_response(response.status)
            for name in ("Content-Type", "x-openclaw-delivery-accepted"):
                value = response.getheader(name)
                if value:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(response_body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(response_body)
        except (OSError, http.client.HTTPException):
            self.send_plain(502, "gateway unavailable")
        finally:
            connection.close()


if __name__ == "__main__":
    ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler).serve_forever()
