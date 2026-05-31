"""Read-only MCP server exposing the scripts stored in this repository."""

import ast
import os
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
ALLOWED_EXTENSIONS = {".ps1", ".py", ".sh"}
MAX_SEARCH_RESULTS = 100

mcp = FastMCP(
    "Scripting Toolkit",
    stateless_http=True,
    json_response=True,
)


def _resolve_script(relative_path: str) -> Path:
    """Resolve a script path and reject access outside scripts/."""
    candidate = (SCRIPTS_ROOT / relative_path).resolve()

    if candidate == SCRIPTS_ROOT or SCRIPTS_ROOT not in candidate.parents:
        raise ValueError("The path must stay inside the scripts directory.")

    if candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Only .ps1, .py, and .sh files can be read.")

    if not candidate.is_file():
        raise FileNotFoundError(f"Script not found: {relative_path}")

    return candidate


def _documentation_files() -> list[Path]:
    """Return visible Markdown files stored in the repository."""
    return sorted(
        path
        for path in REPOSITORY_ROOT.rglob("*.md")
        if path.is_file()
        and not any(part.startswith(".") for part in path.relative_to(REPOSITORY_ROOT).parts)
    )


def _resolve_documentation(relative_path: str) -> Path:
    """Resolve a Markdown path and reject access outside the repository."""
    candidate = (REPOSITORY_ROOT / relative_path).resolve()

    if candidate == REPOSITORY_ROOT or REPOSITORY_ROOT not in candidate.parents:
        raise ValueError("The path must stay inside the repository.")

    if candidate.suffix.lower() != ".md":
        raise ValueError("Only Markdown documentation files can be read.")

    if not candidate.is_file():
        raise FileNotFoundError(f"Documentation file not found: {relative_path}")

    return candidate


def _run_parser(
    command: list[str],
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> dict[str, Any]:
    """Run a syntax parser with a short timeout and return a structured result."""
    try:
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
            env=env,
            input=input_text.encode("utf-8") if input_text is not None else None,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return {"valid": False, "status": "timeout", "message": "Validation timed out."}

    output = "\n".join(
        part.decode("utf-8", errors="replace").strip()
        for part in (result.stdout, result.stderr)
        if part.strip()
    )
    return {
        "valid": result.returncode == 0,
        "status": "valid" if result.returncode == 0 else "invalid",
        "message": output or "Syntax is valid.",
    }


@mcp.tool()
def list_scripts() -> list[str]:
    """List the PowerShell, Python, and Bash scripts available in the repository."""
    return sorted(
        path.relative_to(SCRIPTS_ROOT).as_posix()
        for path in SCRIPTS_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS
    )


@mcp.tool()
def read_script(relative_path: str) -> str:
    """Read one script using a path relative to scripts/, such as linux/setup_api.sh."""
    return _resolve_script(relative_path).read_text(encoding="utf-8")


@mcp.tool()
def search_scripts(query: str) -> list[dict[str, Any]]:
    """Search for text in scripts and return matching paths, line numbers, and excerpts."""
    normalized_query = query.strip().casefold()
    if not normalized_query:
        raise ValueError("The search query must not be empty.")

    matches: list[dict[str, Any]] = []
    for relative_path in list_scripts():
        path = _resolve_script(relative_path)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if normalized_query in line.casefold():
                matches.append(
                    {
                        "path": relative_path,
                        "line": line_number,
                        "excerpt": line.strip(),
                    }
                )
                if len(matches) >= MAX_SEARCH_RESULTS:
                    return matches

    return matches


@mcp.tool()
def describe_script(relative_path: str) -> dict[str, Any]:
    """Return metadata and a short preview for one script."""
    path = _resolve_script(relative_path)
    stat = path.stat()
    preview = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][:5]

    return {
        "path": path.relative_to(SCRIPTS_ROOT).as_posix(),
        "language": {
            ".ps1": "PowerShell",
            ".py": "Python",
            ".sh": "Bash",
        }[path.suffix.lower()],
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "preview": preview,
    }


@mcp.tool()
def validate_script(relative_path: str) -> dict[str, Any]:
    """Check script syntax without executing the script."""
    path = _resolve_script(relative_path)
    suffix = path.suffix.lower()

    if suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            return {
                "valid": False,
                "status": "invalid",
                "message": f"Line {error.lineno}: {error.msg}",
            }
        return {"valid": True, "status": "valid", "message": "Syntax is valid."}

    if suffix == ".sh":
        bash = shutil.which("bash")
        if not bash:
            return {
                "valid": False,
                "status": "unavailable",
                "message": "bash is not installed or is not available in PATH.",
            }

        script = path.read_text(encoding="utf-8").replace("\r\n", "\n")

        if os.name == "nt" and bash.casefold().endswith(r"\windows\system32\bash.exe"):
            wsl = shutil.which("wsl")
            if not wsl or not _run_parser([wsl, "-e", "true"])["valid"]:
                return {
                    "valid": False,
                    "status": "unavailable",
                    "message": "WSL Bash is present, but no Linux distribution is available.",
                }

            return _run_parser([wsl, "-e", "bash", "-n"], input_text=script)

        return _run_parser([bash, "-n"], input_text=script)

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        return {
            "valid": False,
            "status": "unavailable",
            "message": "PowerShell is not installed or is not available in PATH.",
        }

    parser_command = (
        "$errors = $null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:MCP_SCRIPT_PATH, [ref]$null, [ref]$errors) > $null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { $_.Message }; exit 1 }"
    )
    env = {**os.environ, "MCP_SCRIPT_PATH": str(path)}
    return _run_parser([powershell, "-NoProfile", "-Command", parser_command], env=env)


@mcp.tool()
def list_documentation() -> list[str]:
    """List the Markdown documentation files available in the repository."""
    return [path.relative_to(REPOSITORY_ROOT).as_posix() for path in _documentation_files()]


@mcp.tool()
def read_documentation(relative_path: str) -> str:
    """Read one Markdown file using a path relative to the repository root."""
    return _resolve_documentation(relative_path).read_text(encoding="utf-8")


@mcp.tool()
def get_repository_summary() -> dict[str, Any]:
    """Return a short inventory of scripts and documentation in the repository."""
    scripts = list_scripts()
    language_counts = Counter(
        {
            ".ps1": "PowerShell",
            ".py": "Python",
            ".sh": "Bash",
        }[Path(relative_path).suffix.lower()]
        for relative_path in scripts
    )
    category_counts = Counter(Path(relative_path).parts[0] for relative_path in scripts)

    return {
        "repository": REPOSITORY_ROOT.name,
        "script_count": len(scripts),
        "scripts_by_language": dict(sorted(language_counts.items())),
        "scripts_by_category": dict(sorted(category_counts.items())),
        "documentation_count": len(_documentation_files()),
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
