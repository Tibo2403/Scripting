from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "client_cost_savings.py"
SPEC = importlib.util.spec_from_file_location("client_cost_savings", MODULE_PATH)
client_cost_savings = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(client_cost_savings)


def example_config() -> dict:
    return {
        "currency": "EUR",
        "pricing_date": "2026-07-08",
        "period": {
            "users": 25,
            "requests_per_user_per_day": 20,
            "working_days_per_month": 20,
        },
        "tokens": {"input_per_request": 2000, "output_per_request": 800},
        "baseline": {
            "model": "baseline-premium-cloud",
            "input_price_per_1m": 5.0,
            "output_price_per_1m": 15.0,
        },
        "routes": [
            {
                "name": "self-hosted-local",
                "share": 0.45,
                "input_price_per_1m": 0.0,
                "output_price_per_1m": 0.0,
            },
            {
                "name": "cost-optimized-cloud",
                "share": 0.35,
                "input_price_per_1m": 1.0,
                "output_price_per_1m": 4.0,
            },
            {
                "name": "premium-fallback-cloud",
                "share": 0.2,
                "input_price_per_1m": 5.0,
                "output_price_per_1m": 15.0,
            },
        ],
        "fixed_monthly_costs": [
            {"name": "Azure or AWS gateway runtime", "amount": 90.0},
            {"name": "Operations and monitoring", "amount": 100.0},
        ],
        "rate_limits": {"baseline_429_count": 20, "pilot_429_count": 5},
    }


class ClientCostSavingsTest(unittest.TestCase):
    def test_calculates_dynamic_route_prices_with_stable_formula(self) -> None:
        result = client_cost_savings.calculate_savings(example_config())

        self.assertEqual(result["summary"]["monthly_requests"], 10000)
        self.assertEqual(result["summary"]["baseline_provider_cost"], 220.0)
        self.assertEqual(result["summary"]["pilot_provider_cost"], 62.2)
        self.assertEqual(result["summary"]["fixed_monthly_cost"], 190.0)
        self.assertEqual(result["summary"]["pilot_total_cost"], 252.2)
        self.assertEqual(result["summary"]["net_savings"], -32.2)
        self.assertEqual(result["rate_limits"]["avoided_429_count"], 15)

    def test_rejects_route_mix_that_does_not_sum_to_one(self) -> None:
        config = example_config()
        config["routes"][0]["share"] = 0.5

        with self.assertRaisesRegex(ValueError, "route shares must sum to 1.0"):
            client_cost_savings.calculate_savings(config)

    def test_markdown_output_contains_client_report_fields(self) -> None:
        result = client_cost_savings.calculate_savings(example_config())
        markdown = client_cost_savings.format_markdown(result)

        self.assertIn("Pricing date: 2026-07-08", markdown)
        self.assertIn("self-hosted-local", markdown)
        self.assertIn("Avoided 429 errors: 15", markdown)


if __name__ == "__main__":
    unittest.main()
