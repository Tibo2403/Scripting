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
from .metering import EnergyTariff, meter_completion


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--agent", required=True, help="Pseudonymous agent address")
    parser.add_argument("--beneficiary", required=True, help="Allowlisted settlement address")
    parser.add_argument("--prompt-joules-per-token", required=True)
    parser.add_argument("--completion-joules-per-token", required=True)
    parser.add_argument("--euro-per-kwh", required=True)
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
        tariff = EnergyTariff.from_decimal_strings(
            args.prompt_joules_per_token,
            args.completion_joules_per_token,
            args.euro_per_kwh,
        )
        _, measurement = meter_completion(
            args.model,
            [{"role": "user", "content": args.prompt}],
            tariff,
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
            timelock=timelock,
            vault=vault,
            controller=controller,
        )
        pid_receipt = None
        if args.observed_network_velocity_wad is not None:
            pid_receipt = supervisor.update_pid(
                args.agent, args.observed_network_velocity_wad
            )
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
                "operation_id": Web3.to_hex(operation_id),
                "queue_transaction": receipt["transactionHash"].hex(),
                "pid_transaction": (
                    pid_receipt["transactionHash"].hex() if pid_receipt is not None else None
                ),
                "status": "awaiting_vrf_or_scheduled",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
