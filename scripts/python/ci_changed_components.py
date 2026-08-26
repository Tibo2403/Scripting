"""Select CI components from the files changed between two Git revisions."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Iterable


COMPONENTS = (
    "maturity",
    "powershell",
    "bash",
    "python",
    "tokenized",
    "shell_prototypes",
    "pra",
)
MAIN_WORKFLOW = ".github/workflows/script-validation.yml"
EXPERIMENTAL_WORKFLOW = ".github/workflows/experimental-validation.yml"
CREWAI_ROOT = "scripts/python/openclaw_crewai_admin/"


def _normalise(path: str) -> str:
    normalised = path.replace("\\", "/")
    while normalised.startswith("./"):
        normalised = normalised[2:]
    return normalised


def classify_paths(
    paths: Iterable[str], *, top_level_directories_changed: bool = False
) -> dict[str, bool]:
    """Return the CI components affected by *paths*."""
    selected = dict.fromkeys(COMPONENTS, False)

    for raw_path in paths:
        path = _normalise(raw_path)

        if path == MAIN_WORKFLOW:
            for component in ("maturity", "powershell", "bash", "python"):
                selected[component] = True
        if path == EXPERIMENTAL_WORKFLOW:
            for component in ("tokenized", "shell_prototypes", "pra"):
                selected[component] = True

        if path in {
            "project-maturity.toml",
            "scripts/python/check_project_maturity.py",
            "scripts/python/tests/test_check_project_maturity.py",
        }:
            selected["maturity"] = True

        suffix = PurePosixPath(path).suffix.lower()
        if path == "PSScriptAnalyzerSettings.psd1" or (
            path.startswith("scripts/") and suffix in {".ps1", ".psd1", ".psm1"}
        ):
            selected["powershell"] = True
        if path.startswith("scripts/") and suffix == ".sh" and not path.startswith(CREWAI_ROOT):
            selected["bash"] = True
        if (
            path.startswith("scripts/python/")
            and not path.startswith(CREWAI_ROOT)
            and (
                suffix in {".py", ".yaml", ".yml"}
                or path == "scripts/python/requirements.txt"
            )
        ):
            selected["python"] = True

        if path.startswith("tokenized_llm_finance/") and (
            suffix in {".py", ".sol", ".toml", ".txt"}
        ):
            selected["tokenized"] = True
        if path.startswith(
            ("openclaw-akash-dual-agents/", "openclaw-inkling-akash/")
        ) and suffix == ".sh":
            selected["shell_prototypes"] = True
        if (path.startswith("pra/") and suffix in {".ps1", ".psd1", ".psm1"}) or path == (
            "scripts/powershell/Test-ScriptSyntax.ps1"
        ):
            selected["pra"] = True

    if top_level_directories_changed:
        selected["maturity"] = True
    return selected


def _run_git(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return [line for line in result.stdout.splitlines() if line]


def _revision_exists(revision: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
        capture_output=True,
        check=False,
    ).returncode == 0


def _initial_commit_paths(head: str) -> list[str]:
    return _run_git("ls-tree", "-r", "--name-only", head)


def changed_paths(base: str, head: str) -> list[str]:
    """List changed paths, including a safe fallback for an initial push."""
    if not base or set(base) == {"0"} or not _revision_exists(base):
        parents = _run_git("rev-list", "--parents", "-n", "1", head)
        fields = parents[0].split() if parents else []
        if len(fields) < 2:
            return _initial_commit_paths(head)
        base = fields[1]
    return _run_git("diff", "--name-only", "--diff-filter=ACDMRTUXB", f"{base}...{head}")


def top_level_directories(revision: str) -> set[str]:
    return {
        entry.split("\t", 1)[1].rstrip("/")
        for entry in _run_git("ls-tree", "-d", revision)
        if "\t" in entry
    }


def _write_github_output(result: dict[str, bool], output_path: Path) -> None:
    output_path.write_text(
        "".join(f"{name}={str(enabled).lower()}\n" for name, enabled in result.items()),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--all", action="store_true", dest="select_all")
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        if args.select_all:
            result = dict.fromkeys(COMPONENTS, True)
        else:
            paths = changed_paths(args.base, args.head)
            base_directories = (
                top_level_directories(args.base)
                if args.base and set(args.base) != {"0"} and _revision_exists(args.base)
                else set()
            )
            head_directories = top_level_directories(args.head)
            result = classify_paths(
                paths,
                top_level_directories_changed=base_directories != head_directories,
            )
        _write_github_output(result, args.github_output)
    except (OSError, subprocess.CalledProcessError, IndexError) as error:
        print(f"Unable to classify changed files: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
