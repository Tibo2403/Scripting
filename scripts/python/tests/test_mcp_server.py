"""Exercise the read-only tools in an isolated repository without starting HTTP."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "toolkit_mcp_server", Path(__file__).parents[1] / "mcp_server.py"
)
assert SPEC and SPEC.loader
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


class McpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        for name, content in {
            "safe.py": "# Needle\nraise RuntimeError('must never execute')\n",
            "bad.py": "def broken(:\n",
            "safe.sh": "echo Needle\n",
            "safe.ps1": "Write-Output 'Needle'\n",
            "ignored.txt": "ignored",
        }.items():
            (self.scripts / name).write_text(content, encoding="utf-8")
        (self.root / "README.md").write_text("Documentation", encoding="utf-8")
        for name, value in (("REPOSITORY_ROOT", self.root), ("SCRIPTS_ROOT", self.scripts)):
            patcher = patch.object(SERVER, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_inventory_read_metadata_and_summary(self) -> None:
        self.assertEqual(SERVER.list_scripts(), ["bad.py", "safe.ps1", "safe.py", "safe.sh"])
        self.assertIn("Needle", SERVER.read_script("safe.py"))
        self.assertEqual(SERVER.describe_script("safe.py")["language"], "Python")
        self.assertEqual(SERVER.get_repository_summary()["script_count"], 4)
        self.assertEqual(SERVER.list_documentation(), ["README.md"])
        self.assertEqual(SERVER.read_documentation("README.md"), "Documentation")

    def test_rejects_paths_outside_roots_wrong_extensions_and_missing_files(self) -> None:
        for reader, paths in (
            (SERVER.read_script, ["../outside.py", str(self.root / "outside.py"), "ignored.txt", "."]),
            (SERVER.read_documentation, ["../outside.md", str(self.root.parent / "outside.md"), "scripts/safe.py", "."]),
        ):
            for path in paths:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    reader(path)
        for reader, path in ((SERVER.read_script, "missing.py"), (SERVER.read_documentation, "missing.md")):
            with self.assertRaises(FileNotFoundError):
                reader(path)

    def test_search_is_case_insensitive_bounded_and_rejects_empty_queries(self) -> None:
        self.assertEqual(len(SERVER.search_scripts(" nEeDlE ")), 3)
        with patch.object(SERVER, "MAX_SEARCH_RESULTS", 1):
            self.assertEqual(len(SERVER.search_scripts("needle")), 1)
        with self.assertRaises(ValueError):
            SERVER.search_scripts("  ")

    def test_python_validation_does_not_execute_source(self) -> None:
        with patch.object(SERVER.subprocess, "run") as run:
            self.assertTrue(SERVER.validate_script("safe.py")["valid"])
            self.assertFalse(SERVER.validate_script("bad.py")["valid"])
            run.assert_not_called()

    def test_missing_external_parsers(self) -> None:
        with patch.object(SERVER.shutil, "which", return_value=None):
            for name in ("safe.sh", "safe.ps1"):
                self.assertEqual(SERVER.validate_script(name)["status"], "unavailable")

    def test_parser_failure_and_timeout(self) -> None:
        with patch.object(SERVER.subprocess, "run", return_value=subprocess.CompletedProcess([], 2, b"", b"bad syntax")):
            result = SERVER._run_parser(["parser"])
            self.assertFalse(result["valid"])
            self.assertEqual(result["message"], "bad syntax")
        with patch.object(SERVER.subprocess, "run", side_effect=subprocess.TimeoutExpired("parser", 15)):
            self.assertEqual(SERVER._run_parser(["parser"])["status"], "timeout")


if __name__ == "__main__":
    unittest.main()
