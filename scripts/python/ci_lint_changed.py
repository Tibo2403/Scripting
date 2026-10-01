"""Fail on shell lint warnings in changed files (run from the repository root)."""

import argparse
import os
from pathlib import Path
import subprocess

from ci_changed_components import changed_paths


def lint_paths(paths: list[str], language: str) -> None:
    """Lint existing scripts only; deleted paths do not need linting."""
    suffixes = {"bash": {".sh"}, "powershell": {".ps1", ".psm1", ".psd1"}}
    for name in paths:
        path = Path(name)
        if not name.startswith("scripts/") or path.suffix.lower() not in suffixes[language]:
            continue
        if not path.is_file():
            continue
        if language == "bash":
            command = ["shellcheck", "--severity=warning", "--", str(path)]
        else:
            command = [
                "pwsh", "-NoProfile", "-File",
                "scripts/powershell/Test-ScriptWarnings.ps1", "-Path", str(path),
            ]
        subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("language", choices=("bash", "powershell"))
    parser.add_argument("--base", default=os.environ.get("BASE_SHA", ""))
    parser.add_argument("--head", default=os.environ.get("HEAD_SHA") or "HEAD")
    args = parser.parse_args()
    lint_paths(changed_paths(args.base, args.head), args.language)


if __name__ == "__main__":
    main()
