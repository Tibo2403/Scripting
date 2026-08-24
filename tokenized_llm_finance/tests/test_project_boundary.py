"""Regression tests for the tokenized-finance project boundary."""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = PROJECT_ROOT / "python"
FORBIDDEN_IMPORT_ROOTS = {
    "deploy",
    "litellm_scaleway_dispatching",
    "pra",
    "scripts",
}
SOLIDITY_IMPORT_PATTERN = re.compile(
    r'\bimport\b.*?["\']([^"\']+)["\']\s*;', re.MULTILINE | re.DOTALL
)


class ProjectBoundaryTests(unittest.TestCase):
    def test_python_package_does_not_import_sibling_projects(self) -> None:
        violations: list[str] = []

        for source_path in sorted(PYTHON_ROOT.rglob("*.py")):
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
            for node in ast.walk(tree):
                imported_roots: list[str] = []
                if isinstance(node, ast.Import):
                    imported_roots = [alias.name.partition(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported_roots = [node.module.partition(".")[0]]

                forbidden = FORBIDDEN_IMPORT_ROOTS.intersection(imported_roots)
                if forbidden:
                    relative_path = source_path.relative_to(PROJECT_ROOT)
                    violations.append(
                        f"{relative_path}:{node.lineno} imports {', '.join(sorted(forbidden))}"
                    )

        self.assertEqual([], violations, "Cross-project imports found:\n" + "\n".join(violations))

    def test_relative_solidity_imports_stay_inside_project(self) -> None:
        violations: list[str] = []

        for source_directory in ("contracts", "script", "test"):
            for source_path in sorted((PROJECT_ROOT / source_directory).rglob("*.sol")):
                source = source_path.read_text(encoding="utf-8")
                for import_path in SOLIDITY_IMPORT_PATTERN.findall(source):
                    if not import_path.startswith("."):
                        continue
                    resolved_import = (source_path.parent / import_path).resolve()
                    if not resolved_import.is_relative_to(PROJECT_ROOT):
                        relative_path = source_path.relative_to(PROJECT_ROOT)
                        violations.append(f"{relative_path} escapes through {import_path}")

        self.assertEqual([], violations, "Escaping Solidity imports found:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
