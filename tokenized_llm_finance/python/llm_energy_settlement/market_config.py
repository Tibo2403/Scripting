"""Environment-backed construction of the bounded market-pricing service."""

from __future__ import annotations

import os
from pathlib import Path

from .metering import decimal_to_wad
from .pricing import (
    FRANCE_BIDDING_ZONE,
    AdaptiveMarketPricing,
    AdjustmentPolicy,
    EcbFxClient,
    EntsoeDayAheadClient,
    PricingSnapshot,
)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


def _positive_int(name: str, default: str) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def market_snapshot_from_environment() -> PricingSnapshot:
    """Fetch and accept one market snapshot using explicit operational guardrails."""
    try:
        maximum_change_bps = int(os.environ.get("PRICE_MAX_CHANGE_BPS", "1000"))
        maximum_fx_change_bps = int(os.environ.get("FX_MAX_CHANGE_BPS", "500"))
    except ValueError as exc:
        raise ValueError("PRICE_MAX_CHANGE_BPS and FX_MAX_CHANGE_BPS must be integers") from exc
    policy = AdjustmentPolicy(
        minimum_euro_per_kwh_wad=decimal_to_wad(os.environ.get("PRICE_MIN_EUR_PER_KWH", "0.01")),
        maximum_euro_per_kwh_wad=decimal_to_wad(os.environ.get("PRICE_MAX_EUR_PER_KWH", "1.00")),
        maximum_change_bps=maximum_change_bps,
        maximum_electricity_age_seconds=_positive_int("PRICE_MAX_ELECTRICITY_AGE_SECONDS", "7200"),
        maximum_fx_age_seconds=_positive_int("PRICE_MAX_FX_AGE_SECONDS", "345600"),
        minimum_usd_per_eur_wad=decimal_to_wad(os.environ.get("FX_MIN_USD_PER_EUR", "0.50")),
        maximum_usd_per_eur_wad=decimal_to_wad(os.environ.get("FX_MAX_USD_PER_EUR", "2.00")),
        maximum_fx_change_bps=maximum_fx_change_bps,
    )
    pricing = AdaptiveMarketPricing(
        EntsoeDayAheadClient(
            _required("ENTSOE_API_TOKEN"),
            os.environ.get("ENTSOE_BIDDING_ZONE", FRANCE_BIDDING_ZONE),
        ),
        EcbFxClient(),
        policy,
    )
    return pricing.snapshot(Path(os.environ.get("PRICING_STATE_PATH", ".pricing-state.json")))
