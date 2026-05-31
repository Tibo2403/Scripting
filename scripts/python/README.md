# MCP Server

This directory contains a read-only Python MCP server for browsing and checking
the scripts in this repository.

## Tools

- `list_scripts` lists the available PowerShell, Python, and Bash files.
- `read_script` reads a script using a path relative to `scripts/`.
- `search_scripts` searches for text and returns matching lines.
- `describe_script` returns metadata and a short preview.
- `validate_script` checks syntax without executing the script.
- `list_documentation` lists the Markdown documentation files.
- `read_documentation` reads one Markdown file.
- `get_repository_summary` returns script and documentation statistics.

Python validation uses the standard library parser. Bash and PowerShell
validation use `bash -n` and the PowerShell parser when those programs are
available in `PATH`.

## Installation

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\scripts\python\requirements.txt
```

## Run

```powershell
python .\scripts\python\mcp_server.py
```

The Streamable HTTP endpoint is available at:

```text
http://localhost:8000/mcp
```

To inspect the server:

```powershell
npx -y @modelcontextprotocol/inspector
```

Connect the inspector to `http://localhost:8000/mcp`.

## Codex Cost Router

`codex_cost_router.py` is an optional Windows-friendly wrapper for Codex CLI and
a local LiteLLM OSS proxy. It can clean prompts, compress logs, estimate tokens,
apply budgets, and route one-shot Codex tasks to `codex-cheap`, `codex-auto`, or
`codex-strong`.

See [`README_Codex_Cost_Routing.md`](README_Codex_Cost_Routing.md) for setup,
activation, LiteLLM configuration, and usage instructions.
