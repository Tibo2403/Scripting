from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "compute_cost_arbitrage.py"
SPEC = importlib.util.spec_from_file_location("compute_cost_arbitrage", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def scenario() -> dict:
    return {
        "currency": "EUR",
        "pricing_date": "test-snapshot",
        "workload": {
            "monthly_input_tokens": 80_000_000,
            "monthly_output_tokens": 20_000_000,
            "minimum_quality_score": 75,
        },
        "electricity_tariffs": [
            {"name": "high", "price_per_kwh": 0.30},
            {"name": "low", "price_per_kwh": 0.10},
        ],
        "options": [
            {
                "name": "local",
                "type": "self_hosted",
                "litellm_model": "local-llm",
                "quality_score": 80,
                "tokens_per_second": 100,
                "online_hours_per_month": 300,
                "load_power_watts": 500,
                "idle_power_watts": 100,
                "pue": 1,
                "hardware_cost": 1200,
                "residual_value": 0,
                "amortization_months": 24,
                "fixed_monthly_cost": 10,
            },
            {
                "name": "akash",
                "type": "rented_compute",
                "litellm_model": "akash-llm",
                "quality_score": 80,
                "tokens_per_second": 100,
                "billed_hours_per_month": 300,
                "hourly_price": 0.50,
                "fixed_monthly_cost": 0,
            },
            {
                "name": "economy-api",
                "type": "api",
                "litellm_model": "cloud-economy",
                "quality_score": 85,
                "input_price_per_1m": 1,
                "output_price_per_1m": 4,
                "fixed_monthly_cost": 0,
            },
        ],
    }


class ComputeCostArbitrageTests(unittest.TestCase):
    def test_cheapest_eligible_tariff_is_selected(self) -> None:
        report = MODULE.analyze(scenario())

        self.assertEqual(report["recommendation"]["primary"], "local @ low")
        self.assertEqual(report["recommendation"]["primary_litellm_model"], "local-llm")

    def test_quality_floor_can_force_api_choice(self) -> None:
        report = MODULE.analyze(scenario(), minimum_quality_override=83)

        self.assertEqual(report["recommendation"]["primary"], "economy-api")
        local = next(item for item in report["candidates"] if item["name"] == "local")
        self.assertFalse(local["eligible"])
        self.assertFalse(local["quality_ok"])

    def test_capacity_shortage_is_reported(self) -> None:
        config = scenario()
        config["options"][0]["online_hours_per_month"] = 1

        report = MODULE.analyze(config)
        local = next(item for item in report["candidates"] if item["name"] == "local")

        self.assertFalse(local["capacity_ok"])

    def test_break_even_kwh_is_computed_against_api(self) -> None:
        report = MODULE.analyze(scenario())

        self.assertEqual(report["electricity_break_even"][0]["self_hosted"], "local")
        self.assertGreater(report["electricity_break_even"][0]["max_price_per_kwh"], 0)

    def test_unknown_option_type_is_rejected(self) -> None:
        config = scenario()
        config["options"][0]["type"] = "mystery"

        with self.assertRaisesRegex(ValueError, "unsupported option type"):
            MODULE.analyze(config)

    def test_catalog_api_price_is_integrated_and_converted(self) -> None:
        config = scenario()
        config["currency_conversion"] = {"USD": 0.9}
        config["catalog_options"] = [
            {"catalog_id": "api:vendor/model", "quality_score": 90}
        ]
        catalog = {
            "api:vendor/model": {
                "id": "api:vendor/model",
                "name": "vendor/model",
                "type": "api",
                "currency": "USD",
                "litellm_model": "vendor/model",
                "input_price_per_1m": 0.5,
                "output_price_per_1m": 2,
            }
        }

        report = MODULE.analyze(config, catalog=catalog)
        imported = next(item for item in report["candidates"] if item["name"] == "vendor/model")

        self.assertEqual(imported["monthly_cost"], 72.0)
        self.assertEqual(imported["litellm_model"], "vendor/model")

    def test_catalog_requires_currency_conversion(self) -> None:
        config = scenario()
        config["catalog_options"] = [{"catalog_id": "api:model", "quality_score": 90}]
        catalog = {
            "api:model": {
                "id": "api:model", "name": "model", "type": "api", "currency": "USD",
                "input_price_per_1m": 1, "output_price_per_1m": 1,
            }
        }

        with self.assertRaisesRegex(ValueError, "currency_conversion.USD"):
            MODULE.analyze(config, catalog=catalog)

    def test_history_and_daily_weekly_trends_are_exported(self) -> None:
        first = MODULE.analyze(scenario())
        changed = scenario()
        changed["options"][2]["input_price_per_1m"] = 1.5
        second = MODULE.analyze(changed)

        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / "history.csv"
            trend_path = Path(directory) / "trends.csv"
            MODULE.append_history(
                history_path,
                MODULE.history_rows(first, datetime(2026, 7, 6, 8, tzinfo=timezone.utc)),
            )
            MODULE.append_history(
                history_path,
                MODULE.history_rows(second, datetime(2026, 7, 13, 8, tzinfo=timezone.utc)),
            )

            history = MODULE.read_history(history_path)
            trends = MODULE.build_trends(history, ("daily", "weekly"))
            MODULE.export_trends(trend_path, trends)

            api_daily = [
                row for row in trends
                if row["candidate"] == "economy-api" and row["period"] == "daily"
            ]
            api_weekly = [
                row for row in trends
                if row["candidate"] == "economy-api" and row["period"] == "weekly"
            ]
            self.assertEqual(len(history), 8)
            self.assertEqual(len(api_daily), 2)
            self.assertEqual(len(api_weekly), 2)
            self.assertEqual(api_daily[1]["change_from_previous_period"], 40.0)
            self.assertEqual(api_daily[1]["change_pct_from_previous_period"], 25.0)
            self.assertEqual(api_weekly[1]["period_start"], "2026-07-13")
            self.assertIn("average_monthly_cost", trend_path.read_text(encoding="utf-8-sig"))

    def test_append_history_rejects_incompatible_file_without_modifying_it(self) -> None:
        report = MODULE.analyze(scenario())

        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / "history.csv"
            original = "unexpected,header\nkeep,this\n"
            history_path.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "header does not match"):
                MODULE.append_history(
                    history_path,
                    MODULE.history_rows(
                        report, datetime(2026, 7, 13, 8, tzinfo=timezone.utc)
                    ),
                )

            self.assertEqual(history_path.read_text(encoding="utf-8"), original)

if __name__ == "__main__":
    unittest.main()
