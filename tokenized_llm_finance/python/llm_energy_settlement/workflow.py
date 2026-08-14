"""End-to-end metering and queueing command for the autonomous supervisor."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from web3 import Web3

from .chain import OnChainSupervisor, load_contract
from .market_config import market_snapshot_from_environment
from .market_pid import market_adjusted_velocity_wad
from .metering import EnergyTariff, decimal_to_wad, meter_completion


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


def _environment_int(name: str, default: str) -> int:
    value = os.environ.get(name, default).strip()
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--agent", required=True, help="Pseudonymous agent address")
    parser.add_argument("--beneficiary", required=True, help="Allowlisted settlement address")
    parser.add_argument("--prompt-joules-per-token", required=True)
    parser.add_argument("--completion-joules-per-token", required=True)
    parser.add_argument("--euro-per-kwh", help="Manual price; incompatible with market mode")
    parser.add_argument("--tariff-id", help="Manual versioned tariff identifier")
    parser.add_argument(
        "--auto-market-pricing",
        action="store_true",
        help="Use bounded ENTSO-E electricity, ECB FX and LiteLLM provider prices",
    )
    parser.add_argument(
        "--observed-network-velocity-wad",
        type=int,
        help="Optional oracle observation in tokens/second WAD; requires ORACLE_ROLE",
    )
    parser.add_argument("--artifacts", type=Path, default=Path("out"))
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        pricing_snapshot = None
        if args.auto_market_pricing:
            if args.euro_per_kwh or args.tariff_id:
                raise ValueError("Manual tariff options cannot be used with market pricing")
            pricing_snapshot = market_snapshot_from_environment()
            tariff = EnergyTariff(
                prompt_joules_per_token_wad=decimal_to_wad(args.prompt_joules_per_token),
                completion_joules_per_token_wad=decimal_to_wad(args.completion_joules_per_token),
                euro_per_kwh_wad=pricing_snapshot.electricity_euro_per_kwh_wad,
                tariff_id=pricing_snapshot.tariff_id,
            )
        else:
            if not args.euro_per_kwh or not args.tariff_id:
                raise ValueError("Manual mode requires --euro-per-kwh and --tariff-id")
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

        web3 = Web3(Web3.HTTPProvider(_required_environment("RPC_URL")))
        timelock = load_contract(
            web3,
            args.artifacts / "ReversibleRandomTimelock.sol" / "ReversibleRandomTimelock.json",
            _required_environment("TIMELOCK_ADDRESS"),
        )
        vault = load_contract(
            web3,
            args.artifacts / "AgentSettlementVault.sol" / "AgentSettlementVault.json",
            _required_environment("VAULT_ADDRESS"),
        )
        controller = load_contract(
            web3,
            args.artifacts / "PIDBudgetController.sol" / "PIDBudgetController.json",
            _required_environment("PID_CONTROLLER_ADDRESS"),
        )
        supervisor = OnChainSupervisor(
            web3=web3,
            private_key=_required_environment("SUPERVISOR_PRIVATE_KEY"),
            attestor_private_key=_required_environment("METERING_ATTESTOR_PRIVATE_KEY"),
            timelock=timelock,
            vault=vault,
            controller=controller,
            oracle_private_key=os.environ.get("VELOCITY_ORACLE_PRIVATE_KEY") or None,
            confirmations=int(os.environ.get("CHAIN_CONFIRMATIONS", "3")),
            settlement_ttl_seconds=int(os.environ.get("SETTLEMENT_TTL_SECONDS", "21600")),
        )
        pid_receipt = None
        pid_market_adjustment = None
        if args.observed_network_velocity_wad is not None:
            effective_velocity_wad = args.observed_network_velocity_wad
            if pricing_snapshot is not None:
                maximum_velocity_wad = supervisor.maximum_pid_velocity_wad(args.agent)
                effective_velocity_wad, uplift_bps = market_adjusted_velocity_wad(
                    args.observed_network_velocity_wad,
                    pricing_snapshot.electricity_euro_per_kwh_wad,
                    decimal_to_wad(os.environ.get("MARKET_PID_REFERENCE_EUR_PER_KWH", "0.20")),
                    _environment_int("MARKET_PID_MAX_UPLIFT_BPS", "5000"),
                    _environment_int("MARKET_PID_SENSITIVITY_BPS", "10000"),
                    maximum_velocity_wad,
                )
                pid_market_adjustment = {
                    "raw_velocity_wad": args.observed_network_velocity_wad,
                    "effective_velocity_wad": effective_velocity_wad,
                    "electricity_uplift_bps": uplift_bps,
                    "maximum_velocity_wad": maximum_velocity_wad,
                }
            pid_receipt = supervisor.update_pid(args.agent, effective_velocity_wad)
        operation_id, receipt = supervisor.queue_settlement(
            args.agent, args.beneficiary, measurement
        )
    except (OSError, ValueError, RuntimeError, ConnectionError) as exc:
        print(f"workflow failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "measurement": asdict(measurement),
                "pricing": asdict(pricing_snapshot) if pricing_snapshot else None,
                "operation_id": Web3.to_hex(operation_id),
                "queue_transaction": receipt["transactionHash"].hex(),
                "pid_transaction": (
                    pid_receipt["transactionHash"].hex() if pid_receipt is not None else None
                ),
                "pid_market_adjustment": pid_market_adjustment,
                "status": "awaiting_vrf_or_scheduled",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
