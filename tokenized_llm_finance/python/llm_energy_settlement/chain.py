"""web3.py supervisor for PID updates and reversible settlement operations."""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from web3 import Web3
from web3.contract import Contract
from web3.types import TxReceipt

from .metering import UsageMeasurement


def load_contract(web3: Web3, artifact_path: Path, address: str) -> Contract:
    """Load ABI from a Foundry artifact after validating its basic shape."""
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    abi = artifact.get("abi")
    if not isinstance(abi, list):
        raise ValueError(f"Artifact has no ABI array: {artifact_path}")
    return web3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)


@dataclass(slots=True)
class OnChainSupervisor:
    """Signs transactions locally; the key is supplied at runtime and is never logged."""

    web3: Web3
    private_key: str = field(repr=False)
    timelock: Contract
    vault: Contract
    controller: Contract
    confirmations: int = 1
    receipt_timeout_seconds: int = 180
    _account: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.web3.is_connected():
            raise ConnectionError("Cannot connect to the configured RPC endpoint")
        if self.confirmations < 1:
            raise ValueError("confirmations must be positive")
        self._account = self.web3.eth.account.from_key(self.private_key)

    @property
    def address(self) -> str:
        return self._account.address

    def _send(self, function: Any) -> TxReceipt:
        nonce = self.web3.eth.get_transaction_count(self.address, "pending")
        transaction = function.build_transaction(
            {
                "from": self.address,
                "nonce": nonce,
                "chainId": self.web3.eth.chain_id,
            }
        )
        transaction["gas"] = self.web3.eth.estimate_gas(transaction)
        if "gasPrice" not in transaction and "maxFeePerGas" not in transaction:
            transaction["gasPrice"] = self.web3.eth.gas_price
        signed = self.web3.eth.account.sign_transaction(transaction, self.private_key)
        tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.web3.eth.wait_for_transaction_receipt(
            tx_hash, timeout=self.receipt_timeout_seconds
        )
        if receipt["status"] != 1:
            raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")

        target_block = receipt["blockNumber"] + self.confirmations - 1
        while self.web3.eth.block_number < target_block:
            time.sleep(1)
        return receipt

    def update_pid(self, agent: str, observed_velocity_wad: int) -> TxReceipt:
        if observed_velocity_wad < 0:
            raise ValueError("observed_velocity_wad cannot be negative")
        return self._send(
            self.controller.functions.updateBudget(
                Web3.to_checksum_address(agent), observed_velocity_wad
            )
        )

    def queue_settlement(
        self,
        agent: str,
        beneficiary: str,
        measurement: UsageMeasurement,
    ) -> tuple[bytes, TxReceipt]:
        """Encode vault.settle and queue it; VRF later assigns its unpredictable delay."""
        if measurement.settlement_euro_wad <= 0:
            raise ValueError("Refusing to queue a zero-value settlement")
        calldata_hex = self.vault.encode_abi(
            "settle",
            args=[
                Web3.to_checksum_address(agent),
                Web3.to_checksum_address(beneficiary),
                measurement.settlement_euro_wad,
                measurement.usage_digest(),
            ],
        )
        calldata = bytes.fromhex(calldata_hex.removeprefix("0x"))
        salt = secrets.token_bytes(32)
        receipt = self._send(
            self.timelock.functions.queue(self.vault.address, calldata, salt)
        )
        events = self.timelock.events.OperationQueued().process_receipt(receipt)
        if len(events) != 1:
            raise RuntimeError("Expected exactly one OperationQueued event")
        operation_id = events[0]["args"]["operationId"]
        return operation_id, receipt

    def cancel(self, operation_id: bytes) -> TxReceipt:
        return self._send(self.timelock.functions.cancel(operation_id))

    def execute(self, operation_id: bytes) -> TxReceipt:
        return self._send(self.timelock.functions.execute(operation_id))

    def operation(self, operation_id: bytes) -> Any:
        return self.timelock.functions.getOperation(operation_id).call()
