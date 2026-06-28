"""Local-only web form for starting a LiteLLM Codex session with in-memory keys."""

from __future__ import annotations

import argparse
import html
import os
import secrets
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar


DEFAULT_HOST = "127.0.0.1"
DEFAULT_UI_PORT = 8787
DEFAULT_PROXY_PORT = 4000


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex LiteLLM Session Keys</title>
  <style>
    :root {{
      color-scheme: light dark;
      font-family: Segoe UI, system-ui, sans-serif;
      --accent: #1f6feb;
      --ok: #238636;
      --warn: #9a6700;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: color-mix(in srgb, Canvas 94%, CanvasText);
      background: Canvas;
      color: CanvasText;
    }}
    main {{
      width: min(880px, calc(100vw - 32px));
      margin: 28px auto;
      padding: 0 0 28px;
    }}
    h1 {{
      font-size: clamp(24px, 4vw, 34px);
      margin: 0 0 10px;
      letter-spacing: 0;
    }}
    h2 {{
      font-size: 17px;
      margin: 0 0 14px;
    }}
    p {{
      line-height: 1.5;
    }}
    .panel {{
      border: 1px solid color-mix(in srgb, CanvasText 18%, transparent);
      border-radius: 8px;
      padding: 18px;
      margin-top: 16px;
      background: Canvas;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 14px;
    }}
    .provider {{
      border: 1px solid color-mix(in srgb, CanvasText 14%, transparent);
      border-radius: 8px;
      padding: 14px;
      min-height: 96px;
    }}
    .provider strong {{
      display: block;
      margin-bottom: 4px;
    }}
    label {{
      display: block;
      margin-top: 16px;
      font-weight: 600;
    }}
    input {{
      width: 100%;
      box-sizing: border-box;
      margin-top: 6px;
      padding: 11px 12px;
      border-radius: 6px;
      border: 1px solid color-mix(in srgb, CanvasText 24%, transparent);
      font: inherit;
    }}
    input[type="checkbox"] {{
      width: auto;
      margin: 0 8px 0 0;
    }}
    .check {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 10px;
      font-weight: 600;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
    }}
    button {{
      padding: 10px 14px;
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: white;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
    }}
    button.secondary {{
      background: color-mix(in srgb, CanvasText 14%, Canvas);
      color: CanvasText;
    }}
    .status {{
      margin-top: 16px;
      padding: 12px;
      border-radius: 6px;
      background: color-mix(in srgb, var(--accent) 12%, Canvas);
      overflow-wrap: anywhere;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }}
    .pill {{
      border: 1px solid color-mix(in srgb, CanvasText 14%, transparent);
      border-radius: 999px;
      padding: 8px 12px;
      overflow-wrap: anywhere;
    }}
    details {{
      margin-top: 14px;
    }}
    summary {{
      cursor: pointer;
      font-weight: 600;
    }}
    .muted {{
      opacity: .75;
      font-size: 14px;
    }}
    .small {{
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Codex LiteLLM dispatch</h1>
    <p class="muted">Start a local LiteLLM proxy for Codex with cloud keys kept only in this session. Qwen local runs through Ollama and needs no cloud key.</p>
    {status}
    <section class="panel">
      <h2>Providers</h2>
      <div class="grid">
        <div class="provider">
          <strong>OpenAI</strong>
          <span class="muted small">Used for default and deep coding aliases.</span>
        </div>
        <div class="provider">
          <strong>Gemini</strong>
          <span class="muted small">Used for low-cost, long-context, and relief routing.</span>
        </div>
        <div class="provider">
          <strong>Hugging Face</strong>
          <span class="muted small">Optional aliases for HF-hosted open models.</span>
        </div>
        <div class="provider">
          <strong>Qwen local</strong>
          <span class="muted small">{qwen_status}</span>
        </div>
      </div>
      <div class="meta">
        <div class="pill">Proxy URL: <code>http://127.0.0.1:{proxy_port}/v1</code></div>
        <div class="pill">Codex model aliases: <code>codex-light</code>, <code>codex-default</code>, <code>codex-long</code>, <code>codex-deep</code></div>
        <div class="pill">Local fallback: <code>codex-qwen-local</code></div>
      </div>
    </section>

    <section class="panel">
      <h2>Session keys</h2>
      <form method="post" action="/start" autocomplete="off">
        <label for="openai">OpenAI API key</label>
        <input id="openai" name="OPENAI_API_KEY" type="password" placeholder="sk-..." autocomplete="off">
        <label for="gemini">Gemini API key</label>
        <input id="gemini" name="GEMINI_API_KEY" type="password" placeholder="AI..." autocomplete="off">
        <label for="hf">Hugging Face token optional</label>
        <input id="hf" name="HF_TOKEN" type="password" placeholder="hf_..." autocomplete="off">
        <label class="check" for="use_qwen">
          <input id="use_qwen" name="USE_LOCAL_QWEN" type="checkbox" value="1" checked>
          Enable local Qwen fallback through Ollama
        </label>
        <p class="muted small">Qwen is only used as a local Ollama fallback on <code>127.0.0.1:11434</code>; this page never accepts a Qwen API base or key.</p>
        <div class="actions">
          <button type="submit">Start proxy</button>
        </div>
      </form>
      <form method="post" action="/stop">
        <div class="actions">
          <button class="secondary" type="submit">Stop proxy</button>
        </div>
      </form>
    </section>
  </main>
</body>
</html>
"""


def find_litellm(root: Path) -> Path:
    """Find a local LiteLLM executable."""
    candidates = [
        root / "venv" / "Scripts" / "litellm.exe",
        Path(r"C:\tmp\litellm-oss\Scripts\litellm.exe"),
        Path.home() / ".codex" / "litellm-proxy" / "venv" / "Scripts" / "litellm.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("LiteLLM executable not found. Install LiteLLM first.")


def wait_for_port(host: str, port: int, timeout: float = 20.0) -> bool:
    """Wait for a TCP port to accept connections."""
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def local_qwen_status() -> str:
    """Return a short status for the local Ollama Qwen fallback."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/v1/models", timeout=2) as response:
            body = response.read().decode("utf-8", errors="replace")
    except OSError:
        return "Ollama is not reachable on 127.0.0.1:11434."
    if "hf.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF:latest" in body:
        return "Ready through Ollama on 127.0.0.1:11434."
    return "Ollama is running, but the Qwen2.5 Coder model was not found."


class SessionState:
    """Mutable server state."""

    process: subprocess.Popen[str] | None = None
    message = "No session proxy started from this page yet."


class KeySessionHandler(BaseHTTPRequestHandler):
    """Serve the local key form and manage the LiteLLM subprocess."""

    state: ClassVar[SessionState]
    config_path: ClassVar[Path]
    litellm_path: ClassVar[Path]
    proxy_host: ClassVar[str]
    proxy_port: ClassVar[int]

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default request logs so keys never appear in terminal logs."""
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in {"/", "/status"}:
            self.send_error(404)
            return
        self._send_page()

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/start":
            self._start_proxy()
            return
        if self.path == "/stop":
            self._stop_proxy("Session proxy stopped.")
            self._send_page()
            return
        self.send_error(404)

    def _send_page(self) -> None:
        safe_message = html.escape(self.state.message)
        status = f'<div class="status">{safe_message}</div>'
        qwen_status = html.escape(local_qwen_status())
        body = PAGE.format(status=status, proxy_port=self.proxy_port, qwen_status=qwen_status).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
        return {key: values[-1].strip() for key, values in parsed.items()}

    def _start_proxy(self) -> None:
        form = self._read_form()
        openai_key = form.get("OPENAI_API_KEY", "")
        gemini_key = form.get("GEMINI_API_KEY", "")
        hf_token = form.get("HF_TOKEN", "")
        use_local_qwen = form.get("USE_LOCAL_QWEN", "") == "1"
        if not any((openai_key, gemini_key, hf_token, use_local_qwen)):
            self.state.message = "Provide at least one provider key, or keep local Qwen enabled."
            self._send_page()
            return

        self._stop_proxy("Replacing previous session proxy.")
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["LITELLM_API_KEY"] = "sk-local-" + secrets.token_hex(16)
        if openai_key:
            env["OPENAI_API_KEY"] = openai_key
        if gemini_key:
            env["GEMINI_API_KEY"] = gemini_key
        if hf_token:
            env["HF_TOKEN"] = hf_token
            env["HUGGINGFACE_API_KEY"] = hf_token

        try:
            self.state.process = subprocess.Popen(
                [
                    str(self.litellm_path),
                    "--config",
                    str(self.config_path),
                    "--host",
                    self.proxy_host,
                    "--port",
                    str(self.proxy_port),
                ],
                cwd=str(self.config_path.parent),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except OSError as exc:
            self.state.message = f"Unable to start LiteLLM: {exc}"
            self._send_page()
            return

        if wait_for_port(self.proxy_host, self.proxy_port):
            providers = []
            if openai_key:
                providers.append("OpenAI")
            if gemini_key:
                providers.append("Gemini")
            if hf_token:
                providers.append("Hugging Face")
            if use_local_qwen:
                providers.append("Qwen local")
            self.state.message = "Session proxy started with: " + ", ".join(providers)
        else:
            self.state.message = "LiteLLM process started, but the proxy port did not become ready yet."
        self._send_page()

    def _stop_proxy(self, message: str) -> None:
        process = self.state.process
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=8)
        self.state.process = None
        self.state.message = message


def run_server(args: argparse.Namespace) -> int:
    """Run the local key session web server."""
    config_path = Path(args.config).resolve()
    root = config_path.parent
    handler = KeySessionHandler
    handler.state = SessionState()
    handler.config_path = config_path
    handler.litellm_path = find_litellm(root)
    handler.proxy_host = args.proxy_host
    handler.proxy_port = args.proxy_port

    server = ThreadingHTTPServer((args.host, args.ui_port), handler)
    print(f"Open http://{args.host}:{args.ui_port}/ to enter session keys.")
    print(f"LiteLLM proxy will run at http://{args.proxy_host}:{args.proxy_port}/v1.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        handler.state.message = "Stopping web key session."
        if handler.state.process and handler.state.process.poll() is None:
            handler.state.process.terminate()
        return 0
    finally:
        server.server_close()
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--ui-port", type=int, default=DEFAULT_UI_PORT)
    parser.add_argument("--proxy-host", default=DEFAULT_HOST)
    parser.add_argument("--proxy-port", type=int, default=DEFAULT_PROXY_PORT)
    parser.add_argument(
        "--config",
        default=str(Path(__file__).with_name("litellm-cost-routing.yaml")),
        help="LiteLLM YAML config path.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run_server(parse_args(sys.argv[1:])))
