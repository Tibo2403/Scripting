"""Warning checks must propagate failures and preserve path arguments."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci_lint_changed


class ChangedLintTests(unittest.TestCase):
    @patch("ci_lint_changed.subprocess.run")
    @patch("ci_lint_changed.Path.is_file", return_value=True)
    def test_shell_paths_are_single_arguments(self, _exists, run):
        ci_lint_changed.lint_paths(["scripts/bash/a b.sh", "docs/example.sh"], "bash")
        run.assert_called_once_with(
            ["shellcheck", "--severity=warning", "--", str(Path("scripts/bash/a b.sh"))],
            check=True,
        )

    @patch("ci_lint_changed.subprocess.run")
    @patch("ci_lint_changed.Path.is_file", return_value=False)
    def test_deleted_files_are_skipped(self, _exists, run):
        ci_lint_changed.lint_paths(["scripts/gone.ps1"], "powershell")
        run.assert_not_called()

    @patch("ci_lint_changed.subprocess.run", side_effect=subprocess.CalledProcessError(1, "pwsh"))
    @patch("ci_lint_changed.Path.is_file", return_value=True)
    def test_lint_failure_is_fatal(self, _exists, _run):
        with self.assertRaises(subprocess.CalledProcessError):
            ci_lint_changed.lint_paths(["scripts/fail.ps1"], "powershell")


if __name__ == "__main__":
    unittest.main()
