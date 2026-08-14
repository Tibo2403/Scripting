"""Bounded market-pressure transformation for PID oracle observations."""

from __future__ import annotations


def market_adjusted_velocity_wad(
    observed_velocity_wad: int,
    electricity_euro_per_kwh_wad: int,
    reference_euro_per_kwh_wad: int,
    maximum_uplift_bps: int,
    sensitivity_bps: int = 10_000,
    maximum_velocity_wad: int | None = None,
) -> tuple[int, int]:
    """Apply a bounded, one-sided electricity-price surcharge to PID velocity."""
    if observed_velocity_wad < 0 or electricity_euro_per_kwh_wad < 0:
        raise ValueError("Velocity and electricity price cannot be negative")
    if reference_euro_per_kwh_wad <= 0:
        raise ValueError("PID market reference price must be positive")
    if not 0 <= maximum_uplift_bps <= 10_000:
        raise ValueError("PID market maximum uplift must be between 0 and 10000 bps")
    if not 0 <= sensitivity_bps <= 20_000:
        raise ValueError("PID market sensitivity must be between 0 and 20000 bps")
    if maximum_velocity_wad is not None and maximum_velocity_wad <= 0:
        raise ValueError("Maximum PID velocity must be positive")

    uplift_bps = 0
    if electricity_euro_per_kwh_wad > reference_euro_per_kwh_wad:
        raw_premium_bps = (
            (electricity_euro_per_kwh_wad - reference_euro_per_kwh_wad)
            * 10_000
            // reference_euro_per_kwh_wad
        )
        uplift_bps = min(
            raw_premium_bps * sensitivity_bps // 10_000,
            maximum_uplift_bps,
        )

    adjusted = observed_velocity_wad * (10_000 + uplift_bps) // 10_000
    if maximum_velocity_wad is not None:
        adjusted = min(adjusted, maximum_velocity_wad)
    return adjusted, uplift_bps
