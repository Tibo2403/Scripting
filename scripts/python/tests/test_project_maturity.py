"""Tests for the repository project-maturity catalog validator."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.python.check_project_maturity import discover_project_roots, validate_catalog


class ProjectMaturityCatalogTests(unittest.TestCase):
    def test_independent_clone_is_not_a_parent_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "independent" / ".git").mkdir(parents=True)
            (root / "tool").mkdir()
            self.assertEqual(discover_project_roots(root), {"tool"})

    def test_submodule_still_requires_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "submodule").mkdir()
            (root / "submodule" / ".git").write_text(
                "gitdir: ../.git/modules/submodule\n", encoding="utf-8"
            )
            self.assertEqual(discover_project_roots(root), {"submodule"})

    def test_accepts_classified_usable_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "tool").mkdir()
            (root / "README.md").write_text("# Tool\n", encoding="utf-8")
            catalog = {
                "schema_version": 1,
                "projects": [
                    {
                        "path": "tool",
                        "name": "Tool",
                        "status": "usable",
                        "summary": "A tested tool.",
                        "documentation": "README.md",
                        "validation": ["python -m unittest"],
                        "limitations": [],
                    }
                ],
            }

            self.assertEqual(validate_catalog(catalog, root), [])

    def test_rejects_unclassified_root_and_undocumented_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "prototype").mkdir()
            (root / "forgotten").mkdir()
            (root / "README.md").write_text("# Prototype\n", encoding="utf-8")
            catalog = {
                "schema_version": 1,
                "projects": [
                    {
                        "path": "prototype",
                        "name": "Prototype",
                        "status": "experimental",
                        "summary": "An experiment.",
                        "documentation": "README.md",
                        "validation": ["python -m unittest"],
                        "limitations": [],
                    }
                ],
            }

            errors = validate_catalog(catalog, root)

            self.assertTrue(any("limitations" in error for error in errors))
            self.assertIn("unclassified project roots: forgotten", errors)


if __name__ == "__main__":
    unittest.main()
