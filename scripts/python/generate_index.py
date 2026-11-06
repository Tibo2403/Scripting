#!/usr/bin/env python3
"""Generate docs/INDEX.md: a categorized catalog of every script in the repository.

Usage:
    python scripts/python/generate_index.py          # rewrite docs/INDEX.md
    python scripts/python/generate_index.py --check  # fail if docs/INDEX.md is stale
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "INDEX.md"
EXTENSIONS = {".py": "Python", ".ps1": "PowerShell", ".sh": "Bash", ".sol": "Solidity", ".cmd": "Batch"}
SKIP_PARTS = {"tests", "__pycache__", ".github"}


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [Path(line) for line in out.splitlines() if Path(line).suffix in EXTENSIONS]


def describe(path: Path) -> str:
    """Return a one-line description from a docstring, .SYNOPSIS block or leading comment."""
    try:
        text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = text.splitlines()[:40]
    if path.suffix == ".ps1":
        for i, line in enumerate(lines):
            if line.strip().upper() == ".SYNOPSIS" and i + 1 < len(lines):
                return lines[i + 1].strip()
    if path.suffix == ".py":
        match = re.search(r'^\s*(?:"""|\'\'\')\s*(.+?)\s*$', text, re.M)
        if match and match.start() < 400:
            return match.group(1).strip("\"' ")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("#!", "#requires", "# -*-", "@echo")) or not stripped:
            continue
        if stripped.startswith(("#", "//", "::", "REM ")):
            comment = re.sub(r"^(#+|//+|::|REM)\s*", "", stripped).strip()
            if comment and not comment.lower().startswith(("spdx", "pragma", "<#", "requires")):
                return comment
        if not stripped.startswith(("#", "//", "<#")):
            break
    return ""


def category(path: Path) -> str:
    parts = [p for p in path.parts[:-1] if p not in {"scripts"}]
    return " / ".join(parts[:2]) if parts else "(racine)"


def render() -> str:
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in tracked_files():
        if SKIP_PARTS.intersection(path.parts):
            continue
        groups[category(path)].append(path)

    lines = [
        "# Index des scripts",
        "",
        "> Généré par `scripts/python/generate_index.py` — ne pas éditer à la main.",
        "",
        f"{sum(len(v) for v in groups.values())} scripts dans {len(groups)} catégories.",
        "",
        "## Sommaire",
        "",
    ]
    for name in sorted(groups):
        anchor = re.sub(r"[^a-z0-9 _-]", "", name.lower()).replace(" ", "-")
        lines.append(f"- [{name}](#{anchor}) ({len(groups[name])})")
    for name in sorted(groups):
        lines += ["", f"## {name}", "", "| Script | Langage | Description |", "| --- | --- | --- |"]
        for path in sorted(groups[name]):
            desc = describe(path).replace("|", "\\|")[:140]
            link = path.as_posix().replace(" ", "%20")
            lines.append(f"| [`{path.name}`](../{link}) | {EXTENSIONS[path.suffix]} | {desc} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if docs/INDEX.md is out of date")
    args = parser.parse_args()
    content = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print("docs/INDEX.md is out of date. Run: python scripts/python/generate_index.py", file=sys.stderr)
            return 1
        print("docs/INDEX.md is up to date.")
        return 0
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
