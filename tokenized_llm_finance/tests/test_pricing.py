from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from llm_energy_settlement.metering import decimal_to_wad
from llm_energy_settlement.pricing import (
    AdaptiveMarketPricing,
    AdjustmentPolicy,
    EcbFxClient,
    EntsoeDayAheadClient,
    PriceQuote,
    usd_wad_to_euro_wad,
)


class _ElectricityFeed:
    def __init__(self, quote: PriceQuote) -> None:
        self.quote = quote

    def electricity_euro_per_kwh(self, now: datetime | None = None) -> PriceQuote:
        return self.quote


class _FxFeed:
    def __init__(self, quote: PriceQuote) -> None:
        self.quote = quote

    def usd_per_eur(self) -> PriceQuote:
        return self.quote


class PricingTest(unittest.TestCase):
    def test_parses_entsoe_eur_mwh_into_eur_kwh(self) -> None:
        payload = b"""<?xml version="1.0"?>
        <Publication_MarketDocument xmlns="urn:entsoe.eu:wgedi">
          <TimeSeries><Period><timeInterval>
            <start>2026-08-14T10:00Z</start><end>2026-08-14T12:00Z</end>
          </timeInterval><resolution>PT60M</resolution>
          <Point><position>1</position><price.amount>125.50</price.amount></Point>
          </Period></TimeSeries>
        </Publication_MarketDocument>"""
        requested_urls: list[str] = []

        def reader(url: str, timeout: float) -> bytes:
            requested_urls.append(url)
            self.assertGreater(timeout, 0)
            return payload

        client = EntsoeDayAheadClient("secret-token", reader=reader)
        quote = client.electricity_euro_per_kwh(datetime(2026, 8, 14, 10, 30, tzinfo=UTC))

        self.assertEqual(quote.value_wad, decimal_to_wad("0.1255"))
        self.assertIn("documentType=A44", requested_urls[0])

    def test_parses_ecb_usd_per_eur(self) -> None:
        payload = b"""<Envelope><Cube><Cube time="2026-08-14">
          <Cube currency="USD" rate="1.20" />
        </Cube></Cube></Envelope>"""
        quote = EcbFxClient(reader=lambda _url, _timeout: payload).usd_per_eur()

        self.assertEqual(quote.value_wad, decimal_to_wad("1.20"))

    def test_bounds_and_rate_limits_electricity_adjustment(self) -> None:
        now = 1_700_000_000
        policy = AdjustmentPolicy(
            decimal_to_wad("0.01"), decimal_to_wad("1.00"), maximum_change_bps=1_000
        )
        fx = _FxFeed(PriceQuote(decimal_to_wad("1.20"), now, "ECB"))
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "pricing.json"
            first = AdaptiveMarketPricing(
                _ElectricityFeed(PriceQuote(decimal_to_wad("0.20"), now, "ENTSO-E")),
                fx,
                policy,
            ).snapshot(state, now)
            second = AdaptiveMarketPricing(
                _ElectricityFeed(PriceQuote(decimal_to_wad("0.50"), now, "ENTSO-E")),
                fx,
                policy,
            ).snapshot(state, now)

        self.assertEqual(first.electricity_euro_per_kwh_wad, decimal_to_wad("0.20"))
        self.assertEqual(second.electricity_euro_per_kwh_wad, decimal_to_wad("0.22"))

    def test_applies_floor_to_negative_spot_price(self) -> None:
        now = 1_700_000_000
        policy = AdjustmentPolicy(decimal_to_wad("0.01"), decimal_to_wad("1.00"))
        service = AdaptiveMarketPricing(
            _ElectricityFeed(PriceQuote(-decimal_to_wad("0.10"), now, "ENTSO-E")),
            _FxFeed(PriceQuote(decimal_to_wad("1.20"), now, "ECB")),
            policy,
        )
        with tempfile.TemporaryDirectory() as directory:
            result = service.snapshot(Path(directory) / "pricing.json", now)

        self.assertEqual(result.electricity_euro_per_kwh_wad, decimal_to_wad("0.01"))

    def test_rejects_stale_quotes(self) -> None:
        now = 1_700_000_000
        policy = AdjustmentPolicy(decimal_to_wad("0.01"), decimal_to_wad("1.00"))
        service = AdaptiveMarketPricing(
            _ElectricityFeed(PriceQuote(decimal_to_wad("0.20"), now - 7_201, "ENTSO-E")),
            _FxFeed(PriceQuote(decimal_to_wad("1.20"), now, "ECB")),
            policy,
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValueError, "Stale"),
        ):
            service.snapshot(Path(directory) / "pricing.json", now)

    def test_rate_limits_fx_adjustment(self) -> None:
        now = 1_700_000_000
        policy = AdjustmentPolicy(
            decimal_to_wad("0.01"),
            decimal_to_wad("1.00"),
            maximum_fx_change_bps=500,
        )
        electricity = _ElectricityFeed(PriceQuote(decimal_to_wad("0.20"), now, "ENTSO-E"))
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "pricing.json"
            AdaptiveMarketPricing(
                electricity,
                _FxFeed(PriceQuote(decimal_to_wad("1.20"), now, "ECB")),
                policy,
            ).snapshot(state, now)
            adjusted = AdaptiveMarketPricing(
                electricity,
                _FxFeed(PriceQuote(decimal_to_wad("1.50"), now, "ECB")),
                policy,
            ).snapshot(state, now)

        self.assertEqual(adjusted.usd_per_eur_wad, decimal_to_wad("1.26"))

    def test_converts_usd_wad_to_euro_wad(self) -> None:
        self.assertEqual(
            usd_wad_to_euro_wad(decimal_to_wad("1.20"), decimal_to_wad("1.20")),
            10**18,
        )

    def test_rejects_tampered_negative_cached_price(self) -> None:
        now = 1_700_000_000
        policy = AdjustmentPolicy(decimal_to_wad("0.01"), decimal_to_wad("1.00"))
        service = AdaptiveMarketPricing(
            _ElectricityFeed(PriceQuote(decimal_to_wad("0.20"), now, "ENTSO-E")),
            _FxFeed(PriceQuote(decimal_to_wad("1.20"), now, "ECB")),
            policy,
        )
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "pricing.json"
            state.write_text(
                json.dumps(
                    {
                        "electricity_euro_per_kwh_wad": -1,
                        "usd_per_eur_wad": decimal_to_wad("1.20"),
                        "electricity_observed_at": now,
                        "fx_observed_at": now,
                        "electricity_source": "ENTSO-E",
                        "fx_source": "ECB",
                        "generated_at": now,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Invalid pricing state"):
                service.snapshot(state, now)


if __name__ == "__main__":
    unittest.main()
