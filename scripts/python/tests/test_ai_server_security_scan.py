import argparse
import unittest

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
            yes_i_am_authorized=False,
            no_ai=True,
        )
        report = scanner.run_scan(args)
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["planned_ports"], [80, 443])
        self.assertNotIn("ports", report)

    def test_ai_prompt_is_defensive(self):
        prompt = scanner.build_ai_prompt({"findings": [], "target": {"host": "example.com"}})
        self.assertIn("Do not provide exploit instructions", prompt)
        self.assertIn("defensive cybersecurity analyst", prompt)


if __name__ == "__main__":
    unittest.main()
