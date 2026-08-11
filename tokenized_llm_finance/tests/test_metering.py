from __future__ import annotations

import unittest
from types import SimpleNamespace

from llm_energy_settlement.metering import (
    EnergyTariff,
    decimal_to_wad,
    measurement_from_response,
)


def _response(total_tokens: int = 150) -> SimpleNamespace:
    return SimpleNamespace(
        id="req-42",
        model="test/model",
        usage=SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=total_tokens,
        ),
        choices=[SimpleNamespace(message=SimpleNamespace(content="result"))],
    )


class MeteringTest(unittest.TestCase):
    def test_exact_token_energy_euro_pipeline(self) -> None:
        tariff = EnergyTariff.from_decimal_strings("2", "4", "0.25")
        measured = measurement_from_response(_response(), tariff, "fallback")

        self.assertEqual(measured.total_tokens, 150)
        self.assertEqual(measured.energy_joules_wad, 400 * 10**18)
        self.assertEqual(measured.energy_kwh_wad, (400 * 10**18) // 3_600_000)
        self.assertEqual(measured.settlement_euro_wad, measured.energy_kwh_wad // 4)
        self.assertEqual(len(measured.usage_digest()), 32)

    def test_rejects_inconsistent_provider_total(self) -> None:
        tariff = EnergyTariff.from_decimal_strings("1", "1", "1")
        with self.assertRaisesRegex(ValueError, "total_tokens"):
            measurement_from_response(_response(total_tokens=151), tariff, "fallback")

    def test_rejects_more_than_eighteen_decimal_places(self) -> None:
        with self.assertRaisesRegex(ValueError, "18 decimals"):
            decimal_to_wad("0.0000000000000000001")


if __name__ == "__main__":
    unittest.main()
