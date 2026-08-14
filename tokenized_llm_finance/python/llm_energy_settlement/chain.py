"""web3.py clients for PID updates and reversible, attested settlements."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eth_account.messages import encode_typed_data
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import TransactionNotFound
from web3.types import TxReceipt

from .metering import UsageMeasurement


def load_contract(web3: Web3, artifact_path: Path, address: str) -> Contract:
    """Load ABI from a Foundry artifact after validating its basic shape."""
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    abi = artifact.get("abi")
    if not isinstance(abi, list):
        raise ValueError(f"Artifact has no ABI array: {artifact_path}")
    return web3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)


@contextmanager
def _nonce_file_lock(chain_id: int, address: str) -> Iterator[None]:
    """Serialize nonce allocation across processes sharing a signer."""
    lock_name = hashlib.sha256(f"{chain_id}:{address.lower()}".encode()).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"llm-finance-nonce-{lock_name}.lock"
    with lock_path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@dataclass(slots=True)
class OnChainSupervisor:
    """Use distinct runtime keys for proposing, metering, cancellation and execution."""

    web3: Web3
    private_key: str = field(repr=False)
    attestor_private_key: str = field(repr=False)
    timelock: Contract
    vault: Contract
    controller: Contract
    canceller_private_key: str | None = field(default=None, repr=False)
    executor_private_key: str | None = field(default=None, repr=False)
    oracle_private_key: str | None = field(default=None, repr=False)
    confirmations: int = 3
    receipt_timeout_seconds: int = 180
    settlement_ttl_seconds: int = 21_600
    _account: Any = field(init=False, repr=False)
    _attestor_account: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.web3.is_connected():
            raise ConnectionError("Cannot connect to the configured RPC endpoint")
        if self.confirmations < 1 or self.settlement_ttl_seconds < 1:
            raise ValueError("confirmations and settlement_ttl_seconds must be positive")
        self._account = self.web3.eth.account.from_key(self.private_key)
        self._attestor_account = self.web3.eth.account.from_key(self.attestor_private_key)
        if self._account.address == self._attestor_account.address:
            raise ValueError("proposer and metering attestor must use different keys")

    @property
    def address(self) -> str:
        return self._account.address

    def _send(self, function: Any, private_key: str | None = None) -> TxReceipt:
        signing_key = private_key or self.private_key
        account = self.web3.eth.account.from_key(signing_key)
        chain_id = self.web3.eth.chain_id
        with _nonce_file_lock(chain_id, account.address):
            nonce = self.web3.eth.get_transaction_count(account.address, "pending")
            transaction = function.build_transaction(
                {"from": account.address, "nonce": nonce, "chainId": chain_id}
            )
            transaction["gas"] = self.web3.eth.estimate_gas(transaction)
            if "gasPrice" not in transaction and "maxFeePerGas" not in transaction:
                transaction["gasPrice"] = self.web3.eth.gas_price
            signed = self.web3.eth.account.sign_transaction(transaction, signing_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)

        receipt = self.web3.eth.wait_for_transaction_receipt(
            tx_hash, timeout=self.receipt_timeout_seconds
        )
        if receipt["status"] != 1:
            raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
        target_block = receipt["blockNumber"] + self.confirmations - 1
        deadline = time.monotonic() + self.receipt_timeout_seconds
        while self.web3.eth.block_number < target_block:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Confirmation timeout: {tx_hash.hex()}")
            time.sleep(1)

        try:
            canonical_receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            canonical_block = self.web3.eth.get_block(canonical_receipt["blockNumber"])
        except TransactionNotFound as exc:
            message = f"Transaction was removed by a chain reorganization: {tx_hash.hex()}"
            raise RuntimeError(message) from exc
        if (
            canonical_receipt["blockHash"] != receipt["blockHash"]
            or canonical_block["hash"] != canonical_receipt["blockHash"]
        ):
            raise RuntimeError(f"Transaction receipt is not canonical: {tx_hash.hex()}")
        if canonical_receipt["status"] != 1:
            raise RuntimeError(f"Canonical transaction reverted: {tx_hash.hex()}")
        return canonical_receipt

    def update_pid(self, agent: str, observed_velocity_wad: int) -> TxReceipt:
        if observed_velocity_wad < 0:
            raise ValueError("observed_velocity_wad cannot be negative")
        if self.oracle_private_key is None:
            raise ValueError("oracle_private_key is required for PID updates")
        return self._send(
            self.controller.functions.updateBudget(
                Web3.to_checksum_address(agent), observed_velocity_wad
            ),
            self.oracle_private_key,
        )

    def maximum_pid_velocity_wad(self, agent: str) -> int:
        """Read the configured on-chain ceiling used to bound oracle input."""
        state = self.controller.functions.agentState(Web3.to_checksum_address(agent)).call()
        if len(state) <= 4 or not isinstance(state[4], int) or state[4] <= 0:
            raise ValueError("Controller returned an invalid maximum velocity")
        return state[4]

    def _usage_receipt(
        self, agent: str, beneficiary: str, measurement: UsageMeasurement
    ) -> dict[str, Any]:
        epoch_duration = int(self.vault.functions.epochDuration().call())
        maximum_usage_age = int(self.vault.functions.maximumUsageAge().call())
        if epoch_duration <= 0 or maximum_usage_age <= 0:
            raise ValueError("vault time limits must be positive")
        if self.settlement_ttl_seconds > maximum_usage_age:
            raise ValueError("settlement TTL exceeds the vault maximum usage age")
        return {
            "agent": Web3.to_checksum_address(agent),
            "beneficiary": Web3.to_checksum_address(beneficiary),
            "providerRequestId": hashlib.sha256(measurement.request_id.encode()).digest(),
            "modelId": hashlib.sha256(measurement.model.encode()).digest(),
            "tariffId": bytes.fromhex(measurement.tariff_id_sha256),
            "responseHash": bytes.fromhex(measurement.response_text_sha256),
            "promptTokens": measurement.prompt_tokens,
            "completionTokens": measurement.completion_tokens,
            "energyKwhWad": measurement.energy_kwh_wad,
            "euroPerKwhWad": measurement.euro_per_kwh_wad,
            "electricityCostEurWad": measurement.electricity_cost_euro_wad,
            "providerCostUsdWad": measurement.provider_cost_usd_wad,
            "usdPerEurWad": measurement.usd_per_eur_wad,
            "providerCostEurWad": measurement.provider_cost_euro_wad,
            "amountWad": measurement.settlement_euro_wad,
            "usageTimestamp": measurement.usage_timestamp,
            "usageEpoch": measurement.usage_timestamp // epoch_duration,
            "nonce": secrets.randbits(256),
            "deadline": measurement.usage_timestamp + self.settlement_ttl_seconds,
        }

    def _sign_usage_receipt(self, receipt: dict[str, Any]) -> bytes:
        fields = [
            ("agent", "address"),
            ("beneficiary", "address"),
            ("providerRequestId", "bytes32"),
            ("modelId", "bytes32"),
            ("tariffId", "bytes32"),
            ("responseHash", "bytes32"),
            ("promptTokens", "uint256"),
            ("completionTokens", "uint256"),
            ("energyKwhWad", "uint256"),
            ("euroPerKwhWad", "uint256"),
            ("electricityCostEurWad", "uint256"),
            ("providerCostUsdWad", "uint256"),
            ("usdPerEurWad", "uint256"),
            ("providerCostEurWad", "uint256"),
            ("amountWad", "uint256"),
            ("usageTimestamp", "uint256"),
            ("usageEpoch", "uint256"),
            ("nonce", "uint256"),
            ("deadline", "uint256"),
        ]
        typed_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "UsageReceipt": [{"name": name, "type": kind} for name, kind in fields],
            },
            "primaryType": "UsageReceipt",
            "domain": {
                "name": "AgentSettlementVault",
                "version": "1",
                "chainId": self.web3.eth.chain_id,
                "verifyingContract": self.vault.address,
            },
            "message": receipt,
        }
        signable = encode_typed_data(full_message=typed_data)
        return bytes(self._attestor_account.sign_message(signable).signature)

    def queue_settlement(
        self, agent: str, beneficiary: str, measurement: UsageMeasurement
    ) -> tuple[bytes, TxReceipt]:
        """Sign the metering receipt, then queue that immutable settlement payload."""
        if measurement.settlement_euro_wad <= 0 or not measurement.request_id:
            raise ValueError("Refusing a zero-value settlement or empty provider request ID")
        receipt_data = self._usage_receipt(agent, beneficiary, measurement)
        chain_timestamp = int(self.web3.eth.get_block("latest")["timestamp"])
        maximum_queue_delay = int(self.timelock.functions.minimumDelay().call()) + int(
            self.timelock.functions.noiseWindow().call()
        )
        if receipt_data["deadline"] <= chain_timestamp + maximum_queue_delay:
            raise ValueError("settlement will expire before its maximum queue delay")
        signature = self._sign_usage_receipt(receipt_data)
        calldata_hex = self.vault.encode_abi("settle", args=[receipt_data, signature])
        calldata = bytes.fromhex(calldata_hex.removeprefix("0x"))
        semantic_key = self.vault.functions.hashUsageReceipt(receipt_data).call()
        queue_receipt = self._send(
            self.timelock.functions.queue(self.vault.address, calldata, semantic_key)
        )
        events = self.timelock.events.OperationQueued().process_receipt(queue_receipt)
        if len(events) != 1:
            raise RuntimeError("Expected exactly one OperationQueued event")
        return events[0]["args"]["operationId"], queue_receipt

    def cancel(self, operation_id: bytes) -> TxReceipt:
        if self.canceller_private_key is None:
            raise ValueError("canceller_private_key is required")
        return self._send(self.timelock.functions.cancel(operation_id), self.canceller_private_key)

    def execute(self, operation_id: bytes) -> TxReceipt:
        if self.executor_private_key is None:
            raise ValueError("executor_private_key is required")
        return self._send(self.timelock.functions.execute(operation_id), self.executor_private_key)

    def operation(self, operation_id: bytes) -> Any:
        return self.timelock.functions.getOperation(operation_id).call()
