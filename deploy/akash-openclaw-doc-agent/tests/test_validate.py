"""Regression tests for the Akash deployment invariant validator."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

VALIDATOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate.py"
SPEC = importlib.util.spec_from_file_location("akash_validator", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to import validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
validate = VALIDATOR.validate


class DeploymentValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.root = Path(self.temp_directory.name) / "project"
        shutil.copytree(Path(__file__).resolve().parents[1], self.root)
        self.repository_root = Path(self.temp_directory.name) / "repository"
        workflow_target = self.repository_root / ".github" / "workflows"
        workflow_target.mkdir(parents=True)
        shutil.copy2(
            Path(__file__).resolve().parents[3]
            / ".github"
            / "workflows"
            / "akash-openclaw-doc-agent.yml",
            workflow_target / "akash-openclaw-doc-agent.yml",
        )

    def test_checked_in_configuration_is_valid(self) -> None:
        self.assertEqual(validate(self.root, self.repository_root), [])

    def test_dangerous_allowed_tool_is_rejected(self) -> None:
        path = self.root / "config" / "openclaw.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["tools"]["allow"].append("exec")
        path.write_text(json.dumps(config), encoding="utf-8")

        self.assertIn("Unexpected allowed tool.", validate(self.root, self.repository_root))

    def test_malformed_configuration_fails_cleanly(self) -> None:
        (self.root / "config" / "openclaw.json").write_text("{", encoding="utf-8")

        errors = validate(self.root, self.repository_root)

        self.assertEqual(len(errors), 1)
        self.assertIn("Unable to load deployment inputs", errors[0])

    def test_mutable_base_image_is_rejected(self) -> None:
        path = self.root / "Dockerfile"
        content = path.read_text(encoding="utf-8")
        content = content.replace(
            "@sha256:ae7ff536446f1bbb57ea51b9b21097d8f299d30d683dcd72644973bc0522f3b3",
            "",
        )
        path.write_text(content, encoding="utf-8")

        self.assertIn(
            "Both base images must be pinned by tag and sha256 digest.",
            validate(self.root, self.repository_root),
        )


if __name__ == "__main__":
    unittest.main()
