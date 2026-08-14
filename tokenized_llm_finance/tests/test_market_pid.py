from __future__ import annotations

import unittest

from llm_energy_settlement.market_pid import market_adjusted_velocity_wad
from llm_energy_settlement.metering import decimal_to_wad


class MarketPidTest(unittest.TestCase):
    def test_applies_bounded_price_pressure(self) -> None:
        adjusted, uplift_bps = market_adjusted_velocity_wad(
            decimal_to_wad("100"),
            decimal_to_wad("0.30"),
            decimal_to_wad("0.20"),
            maximum_uplift_bps=2_500,
        )

        self.assertEqual(uplift_bps, 2_500)
        self.assertEqual(adjusted, decimal_to_wad("125"))

    def test_does_not_increase_signal_below_reference(self) -> None:
        observed = decimal_to_wad("100")
        adjusted, uplift_bps = market_adjusted_velocity_wad(
            observed,
            decimal_to_wad("0.10"),
            decimal_to_wad("0.20"),
            maximum_uplift_bps=5_000,
        )

        self.assertEqual((adjusted, uplift_bps), (observed, 0))

    def test_caps_signal_at_on_chain_maximum(self) -> None:
        adjusted, uplift_bps = market_adjusted_velocity_wad(
            decimal_to_wad("90"),
            decimal_to_wad("0.30"),
            decimal_to_wad("0.20"),
            maximum_uplift_bps=5_000,
            maximum_velocity_wad=decimal_to_wad("100"),
        )

        self.assertEqual(uplift_bps, 5_000)
        self.assertEqual(adjusted, decimal_to_wad("100"))

    def test_rejects_unsafe_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "reference"):
            market_adjusted_velocity_wad(1, 1, 0, 100)
        with self.assertRaisesRegex(ValueError, "maximum uplift"):
            market_adjusted_velocity_wad(1, 1, 1, 10_001)


if __name__ == "__main__":
    unittest.main()
