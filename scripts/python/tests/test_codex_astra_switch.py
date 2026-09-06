import importlib.util
from pathlib import Path
import tempfile
import tomllib
import unittest

SPEC = importlib.util.spec_from_file_location("astra_switch", Path(__file__).resolve().parents[1] / "codex_astra_switch.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SwitchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.switch = MODULE.Switch(Path(self.temp.name))

    def test_restore_preserves_other_edits_and_original_model(self):
        original = 'model = "original"\nmodel_provider = "openai"\n[features]\nx = true\n'
        self.switch.config.write_text(original, encoding="utf-8")
        self.switch.activate()
        self.switch.activate()
        self.assertTrue(self.switch.enabled())
        text = self.switch.read().replace("x = true", "x = false")
        self.switch.config.write_text(text, encoding="utf-8", newline="")
        self.switch.deactivate()
        self.switch.deactivate()
        data = tomllib.loads(self.switch.read())
        self.assertEqual(data["model"], "original")
        self.assertFalse(data["features"]["x"])
        self.assertNotIn(MODULE.PROVIDER, data.get("model_providers", {}))

    def test_absent_model_assignments_restored(self):
        self.switch.config.write_text('#model = "example"\n[features]\nx = true\n', encoding="utf-8")
        self.switch.activate()
        self.switch.deactivate()
        self.assertNotIn("model", tomllib.loads(self.switch.read()))
        self.assertIn('#model = "example"', self.switch.read())

    def test_concurrent_model_edit_is_not_overwritten(self):
        self.switch.activate()
        self.switch.config.write_text(self.switch.read().replace('model = "gpt-6-astra"', 'model = "another"'), encoding="utf-8", newline="")
        with self.assertRaises(RuntimeError):
            self.switch.deactivate()
        self.assertTrue(self.switch.state.exists())

    def test_invalid_toml_unchanged(self):
        self.switch.config.write_text("[broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.switch.activate()
        self.assertFalse(self.switch.state.exists())


if __name__ == "__main__":
    unittest.main()
