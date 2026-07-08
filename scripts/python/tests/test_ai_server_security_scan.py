import argparse
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "ai_server_security_scan.py"
if str(MODULE_PATH.parent) not in sys.path:
    sys.path.insert(0, str(MODULE_PATH.parent))

import ai_server_security_scan as scanner


class AiServerSecurityScanTests(unittest.TestCase):
    def test_parse_ports_accepts_ranges_and_sorts_unique_ports(self):
        self.assertEqual(scanner.parse_ports("443,80,80,8000-8002"), [80, 443, 8000, 8001, 8002])

    def test_parse_ports_rejects_invalid_range(self):
        with self.assertRaises(ValueError):
            scanner.parse_ports("9000-8999")

    def test_normalize_target_rejects_ranges_and_wildcards(self):
        for target in ("192.0.2.0/24", "*.example.com", "example.com other"):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    scanner.normalize_target(target)

    def test_normalize_target_accepts_url(self):
        host, scheme = scanner.normalize_target("https://example.com/app")
        self.assertEqual(host, "example.com")
        self.assertEqual(scheme, "https")

    def test_local_findings_flags_missing_http_security_headers(self):
        ports = [scanner.PortObservation(port=443, status="open", risk="info", notes=["HTTPS open."])]
        findings = scanner.local_findings(
            ports,
            [{"url": "https://example.com:443/", "status": 200, "headers": {}, "error": ""}],
            [],
        )
        titles = {finding["title"] for finding in findings}
        self.assertIn("Missing HTTP security header: strict-transport-security", titles)
        self.assertIn("Open TCP port 443", titles)

    def test_dry_run_has_no_network_results(self):
        args = argparse.Namespace(
            target="example.com",
            ports="80,443",
            dry_run=True,
            business_context="production-smb",
            data_class="personal-data",
            exposure="internet",
            yes_i_am_authorized=False,
            no_ai=True,
        )
        report = scanner.run_scan(args)
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["planned_ports"], [80, 443])
        self.assertEqual(report["context"]["business_context"], "production-smb")
        self.assertEqual(report["context"]["data_class"], "personal-data")
        self.assertEqual(report["context"]["exposure"], "internet")
        self.assertNotIn("ports", report)

    def test_enrich_findings_prioritizes_internet_datastore(self):
        findings = [
            {
                "severity": "high",
                "title": "Open TCP port 6379",
                "evidence": "Service hint: redis",
                "recommendation": "Restrict Redis to trusted networks.",
            },
            {
                "severity": "low",
                "title": "Missing HTTP security header: x-frame-options",
                "evidence": "https://example.com:443/",
                "recommendation": "Set X-Frame-Options or CSP frame-ancestors.",
            },
        ]
        enriched = scanner.enrich_findings(findings, exposure="internet")
        self.assertEqual(enriched[0]["title"], "Open TCP port 6379")
        self.assertGreaterEqual(enriched[0]["priority_score"], 90)
        self.assertIn("data-store", enriched[0]["triage_tags"])
        self.assertIn("internet-exposed", enriched[0]["triage_tags"])
        self.assertEqual(enriched[0]["estimated_effort"], "same-day containment")

    def test_build_ai_triage_and_remediation_plan_are_local(self):
        report = {
            "target": {"host": "example.com"},
            "ports": [{"port": 3389, "status": "open"}],
            "findings": scanner.enrich_findings(
                [
                    {
                        "severity": "high",
                        "title": "Open TCP port 3389",
                        "evidence": "Service hint: rdp",
                        "recommendation": "Restrict RDP access.",
                    }
                ],
                exposure="internet",
            ),
        }
        report["ai_triage"] = scanner.build_ai_triage(report)
        report["local_remediation_plan"] = scanner.build_local_remediation_plan(report)
        self.assertEqual(report["ai_triage"]["risk_posture"], "needs immediate containment")
        self.assertIn(3389, report["ai_triage"]["open_ports"])
        self.assertIn("Day-one remediation order", report["local_remediation_plan"])

    def test_markdown_includes_priority_and_local_plan(self):
        report = {
            "generated_at": "2026-07-08T00:00:00+00:00",
            "target": {"host": "example.com"},
            "context": {"business_context": "smb", "data_class": "personal-data", "exposure": "internet"},
            "authorization_confirmed": True,
            "ai_analysis": "",
            "ai_triage": {"risk_posture": "manageable with hardening"},
            "ports": [{"port": 443, "status": "open", "service_hint": "https", "risk": "info", "notes": []}],
            "findings": [
                {
                    "severity": "low",
                    "title": "Missing HTTP security header: x-content-type-options",
                    "evidence": "https://example.com:443/",
                    "recommendation": "Set X-Content-Type-Options.",
                    "priority_score": 35,
                    "triage_tags": ["web-hardening"],
                    "day_one_action": "Confirm the service is expected and keep it in the evidence log.",
                    "verification": "Re-run this scanner.",
                }
            ],
            "local_remediation_plan": "Local AI-style triage: manageable with hardening.",
        }
        markdown = scanner.render_markdown(report)
        self.assertIn("| Score | Severity | Finding | Tags | Day-one action |", markdown)
        self.assertIn("## Local Remediation Plan", markdown)
        self.assertIn("personal-data", markdown)

    def test_ai_prompt_is_defensive(self):
        prompt = scanner.build_ai_prompt({"findings": [], "target": {"host": "example.com"}})
        self.assertIn("Do not provide exploit instructions", prompt)
        self.assertIn("priority_score", prompt)
        self.assertIn("defensive cybersecurity analyst", prompt)


if __name__ == "__main__":
    unittest.main()
