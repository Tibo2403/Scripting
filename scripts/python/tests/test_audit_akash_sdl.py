from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).parents[1] / "audit_akash_sdl.py"
SPEC = importlib.util.spec_from_file_location("audit_akash_sdl", MODULE_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


class AuditAkashSdlTests(unittest.TestCase):
    def secure_document(self):
        return {
            "version": "2.0",
            "services": {
                "ollama": {
                    "image": "ollama/ollama@sha256:" + "a" * 64,
                    "expose": [{"port": 11434, "to": [{"service": "litellm"}]}],
                },
                "litellm": {
                    "image": "ghcr.io/berriai/litellm:v1.83.14-stable.patch.3",
                    "env": ["LITELLM_MASTER_KEY=REDACTED"],
                    "expose": [
                        {
                            "port": 4000,
                            "to": [{"global": True}],
                            "http_options": {
                                "max_body_size": 10 * 1024 * 1024,
                                "read_timeout": 60_000,
                                "send_timeout": 60_000,
                            },
                        }
                    ],
                },
            },
        }

    def test_parse_args_defaults_public_service_to_litellm(self):
        args = AUDIT.parse_args(["example.yml"])
        self.assertEqual(args.public_service, "litellm")

    def test_accepts_minimum_baseline_with_only_digest_advisory_absent(self):
        findings = AUDIT.audit(self.secure_document(), "litellm")
        self.assertFalse(any(item.severity == "ERROR" for item in findings))

    def test_rejects_latest_public_backend_and_missing_http_limits(self):
        document = self.secure_document()
        document["services"]["ollama"]["image"] = "ollama/ollama:latest"
        document["services"]["ollama"]["expose"] = [{"port": 11434, "to": [{"global": True}]}]
        messages = [item.message for item in AUDIT.audit(document, "litellm") if item.severity == "ERROR"]
        self.assertTrue(any("pin an explicit version" in message for message in messages))
        self.assertIn("backend is globally exposed", messages)
        self.assertIn("global HTTP port needs http_options limits", messages)

    def test_sanitize_redacts_named_and_inline_secrets(self):
        document = self.secure_document()
        document["services"]["litellm"]["env"] = ["LITELLM_MASTER_KEY=sk-secretvalue12345"]
        document["services"]["litellm"]["args"] = ["use sk-anothersecret123"]
        sanitized = AUDIT.sanitize(document)
        service = sanitized["services"]["litellm"]
        self.assertEqual(service["env"], ["LITELLM_MASTER_KEY=REDACTED"])
        self.assertEqual(service["args"], ["use REDACTED"])

    def test_audit_warns_on_inline_secret_values_without_sensitive_env_name(self):
        document = self.secure_document()
        document["services"]["litellm"]["env"] = ["UPSTREAM_URL=https://proxy.local/sk-secretvalue12345"]
        document["services"]["litellm"]["command"] = "serve --token sk-anothersecret123"
        warnings = [item.location for item in AUDIT.audit(document, "litellm") if item.severity == "WARN"]
        self.assertIn("services.litellm.env.UPSTREAM_URL", warnings)
        self.assertIn("services.litellm.command", warnings)


if __name__ == "__main__":
    unittest.main()
