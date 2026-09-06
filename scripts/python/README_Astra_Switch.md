# Codex / LiteLLM Astra switch (Windows)

Double-click `Codex-Proxy-Astra.cmd` at the repository root. ON starts a dedicated
LiteLLM route on `127.0.0.1:4002` and selects it in Codex. OFF restores the previous
root model/provider settings, preserving unrelated config edits. Restart Codex and
open a new task after either operation; existing tasks may retain model overrides.

The local service remains on standby after OFF or closing the panel. OFF switches
Codex routing, not the Windows process. A PC restart stops the service. No autostart
or automatic activation is installed. The endpoint is loopback-only and has no
proxy authentication; other processes on this PC can use it while running.

Requires Windows, the bundled Codex Python (3.11+, Tkinter), and the existing
`~/.codex/litellm-proxy/start_litellm_proxy.py` with its LiteLLM environment.
ON requires an OpenAI API key with access to `gpt-6-astra`. Enter it in the masked
field or supply `OPENAI_API_KEY` in the launching shell. It is inherited by the
proxy process, never saved by the panel. ChatGPT subscription login is not reused.
API usage is billed to that key. No fallback to another model is configured.

The readiness check verifies the local advertised model, not account permission
or a complete Responses/tool-call request. An upstream API error can still occur.

Files created under `CODEX_HOME` (default `~/.codex`):

- `astra-switch-state.json`: original model/provider lines for OFF; no full config backup.
- `config.toml`: root model/provider and a marked, dedicated provider block.
- `litellm-proxy/astra-switch.yaml`: isolated Astra route with environment key reference.
- `litellm-proxy/astra-switch.log`: local server diagnostics; do not share unchecked.

CLI from the repository root:

```powershell
.\Codex-Proxy-Astra.cmd status
.\Codex-Proxy-Astra.cmd on
.\Codex-Proxy-Astra.cmd off
```

If another tool changes the selected model while ON, OFF refuses to overwrite it.
Keep the state file and reconcile the two model settings before retrying OFF.

Validation: `python -m unittest discover -s scripts/python/tests -p test_codex_astra_switch.py -v`.
