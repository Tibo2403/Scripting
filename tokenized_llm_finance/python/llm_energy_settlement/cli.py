"""Minimal command-line entry point for a metered LLM call and optional queueing."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .metering import EnergyTariff, meter_completion


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="LiteLLM model identifier")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--prompt-joules-per-token", required=True)
    parser.add_argument("--completion-joules-per-token", required=True)
    parser.add_argument("--euro-per-kwh", required=True)
    parser.add_argument("--output", type=Path, help="Optional local JSON measurement file")
    return parser


def main() -> int:
    args = _parser().parse_args()
    tariff = EnergyTariff.from_decimal_strings(
        args.prompt_joules_per_token,
        args.completion_joules_per_token,
        args.euro_per_kwh,
    )
    try:
        _, measurement = meter_completion(
            args.model,
            [{"role": "user", "content": args.prompt}],
            tariff,
        )
    except (ValueError, RuntimeError, ConnectionError) as exc:
        print(f"metering failed: {exc}", file=sys.stderr)
        return 1

    serialized = json.dumps(asdict(measurement), indent=2, sort_keys=True)
    print(serialized)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
