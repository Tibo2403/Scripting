"""Tests for immutable Akash SDL rendering."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_deploy.py"
SPEC = importlib.util.spec_from_file_location("render_deploy", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to import renderer from {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

AGENT = "ghcr.io/example/repo/agent:2026.08.27-1@sha256:" + "a" * 64
OLLAMA = "ghcr.io/example/repo/ollama:2026.08.27-1@sha256:" + "b" * 64


class RenderDeployTests(unittest.TestCase):
    def test_renders_only_digest_pinned_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "deploy.yaml"
            MODULE.render(
                Path(__file__).resolve().parents[1] / "deploy.yaml",
                output,
                AGENT,
                OLLAMA,
            )
            rendered = output.read_text(encoding="utf-8")

        self.assertIn(f"image: {AGENT}", rendered)
        self.assertIn(f"image: {OLLAMA}", rendered)
        self.assertNotIn("__AGENT_IMAGE__", rendered)

    def test_rejects_tag_only_reference_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "deploy.yaml"
            with self.assertRaisesRegex(ValueError, "sha256 digest"):
                MODULE.render(
                    Path(__file__).resolve().parents[1] / "deploy.yaml",
                    output,
                    "ghcr.io/example/repo/agent:2026.08.27-1",
                    OLLAMA,
                )
            self.assertFalse(output.exists())

    def test_rejects_latest_even_with_digest(self) -> None:
        with self.assertRaisesRegex(ValueError, "latest"):
            MODULE.validate_image_reference(
                "ghcr.io/example/repo/agent:latest@sha256:" + "c" * 64
            )


if __name__ == "__main__":
    unittest.main()
