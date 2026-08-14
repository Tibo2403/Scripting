"""Minimal command-line entry point for a metered LLM call and optional queueing."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .market_config import market_snapshot_from_environment
from .metering import EnergyTariff, decimal_to_wad, meter_completion


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="LiteLLM model identifier")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--prompt-joules-per-token", required=True)
    parser.add_argument("--completion-joules-per-token", required=True)
    parser.add_argument("--euro-per-kwh", help="Manual EUR/kWh price")
    parser.add_argument("--tariff-id", default="manual-v1")
    parser.add_argument("--auto-market-pricing", action="store_true")
    parser.add_argument("--output", type=Path, help="Optional local JSON measurement file")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        pricing_snapshot = None
        if args.auto_market_pricing:
            if args.euro_per_kwh:
                raise ValueError("--euro-per-kwh cannot be used with market pricing")
            pricing_snapshot = market_snapshot_from_environment()
            tariff = EnergyTariff(
                prompt_joules_per_token_wad=decimal_to_wad(args.prompt_joules_per_token),
                completion_joules_per_token_wad=decimal_to_wad(args.completion_joules_per_token),
                euro_per_kwh_wad=pricing_snapshot.electricity_euro_per_kwh_wad,
                tariff_id=pricing_snapshot.tariff_id,
            )
        else:
            if not args.euro_per_kwh:
                raise ValueError("Manual mode requires --euro-per-kwh")
            tariff = EnergyTariff.from_decimal_strings(
                args.prompt_joules_per_token,
                args.completion_joules_per_token,
                args.euro_per_kwh,
                args.tariff_id,
            )
        _, measurement = meter_completion(
            args.model,
            [{"role": "user", "content": args.prompt}],
            tariff,
            usd_per_eur_wad=(pricing_snapshot.usd_per_eur_wad if pricing_snapshot else 10**18),
            include_provider_cost=pricing_snapshot is not None,
        )
    except (ValueError, RuntimeError, ConnectionError) as exc:
        print(f"metering failed: {exc}", file=sys.stderr)
        return 1

    serialized = json.dumps(
        {
            "measurement": asdict(measurement),
            "pricing": asdict(pricing_snapshot) if pricing_snapshot else None,
        },
        indent=2,
        sort_keys=True,
    )
    print(serialized)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
