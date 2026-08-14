"""Deterministic LiteLLM token-to-energy-to-EUR metering."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

WAD = 10**18
JOULES_PER_KWH = 3_600_000


def decimal_to_wad(value: str | Decimal) -> int:
    """Convert a base-10 value to WAD, rejecting precision beyond 18 decimals."""
    try:
        scaled = Decimal(value) * WAD
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc
    if not scaled.is_finite() or scaled != scaled.to_integral_value():
        raise ValueError(f"Value cannot be represented exactly with 18 decimals: {value!r}")
    result = int(scaled)
    if result < 0:
        raise ValueError("Economic coefficients must be non-negative")
    return result


@dataclass(frozen=True, slots=True)
class EnergyTariff:
    """Measured energy coefficients and electricity tariff, all stored as WAD integers."""

    prompt_joules_per_token_wad: int
    completion_joules_per_token_wad: int
    euro_per_kwh_wad: int
    tariff_id: str = "default-v1"

    @classmethod
    def from_decimal_strings(
        cls,
        prompt_joules_per_token: str,
        completion_joules_per_token: str,
        euro_per_kwh: str,
        tariff_id: str = "default-v1",
    ) -> EnergyTariff:
        return cls(
            prompt_joules_per_token_wad=decimal_to_wad(prompt_joules_per_token),
            completion_joules_per_token_wad=decimal_to_wad(completion_joules_per_token),
            euro_per_kwh_wad=decimal_to_wad(euro_per_kwh),
            tariff_id=tariff_id,
        )

    def __post_init__(self) -> None:
        if not self.tariff_id.strip():
            raise ValueError("tariff_id is required")
        if (
            min(
                self.prompt_joules_per_token_wad,
                self.completion_joules_per_token_wad,
                self.euro_per_kwh_wad,
            )
            < 0
        ):
            raise ValueError("Economic coefficients must be non-negative")


@dataclass(frozen=True, slots=True)
class UsageMeasurement:
    request_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    energy_joules_wad: int
    energy_kwh_wad: int
    euro_per_kwh_wad: int
    electricity_cost_euro_wad: int
    provider_cost_usd_wad: int
    usd_per_eur_wad: int
    provider_cost_euro_wad: int
    settlement_euro_wad: int
    response_text_sha256: str
    tariff_id_sha256: str
    usage_timestamp: int

    def usage_digest(self) -> bytes:
        """Return a replay-resistant digest suitable for Solidity bytes32."""
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).digest()


def _field(container: Any, name: str, default: Any = None) -> Any:
    if isinstance(container, Mapping):
        return container.get(name, default)
    return getattr(container, name, default)


def _response_text(response: Any) -> str:
    choices = _field(response, "choices", [])
    if not choices:
        return ""
    message = _field(choices[0], "message")
    content = _field(message, "content", "")
    return content if isinstance(content, str) else json.dumps(content, sort_keys=True, default=str)


def measurement_from_response(
    response: Any,
    tariff: EnergyTariff,
    requested_model: str,
    measured_at: int | None = None,
    provider_cost_usd_wad: int = 0,
    usd_per_eur_wad: int = WAD,
) -> UsageMeasurement:
    """Read exact provider-reported prompt/completion counters from a LiteLLM response."""
    usage = _field(response, "usage")
    if usage is None:
        raise ValueError("LiteLLM response has no usage counters; settlement is refused")

    prompt_tokens = _field(usage, "prompt_tokens")
    completion_tokens = _field(usage, "completion_tokens")
    if not isinstance(prompt_tokens, int) or not isinstance(completion_tokens, int):
        raise ValueError("Provider usage counters must be integers")
    if prompt_tokens < 0 or completion_tokens < 0:
        raise ValueError("Provider usage counters cannot be negative")
    total_tokens = prompt_tokens + completion_tokens
    provider_total = _field(usage, "total_tokens")
    if provider_total is not None and provider_total != total_tokens:
        raise ValueError("Provider total_tokens differs from prompt_tokens + completion_tokens")

    # Exact integer pipeline:
    # energy_joules_WAD = prompt_tokens*J_prompt_WAD + completion_tokens*J_completion_WAD
    # energy_kWh_WAD    = energy_joules_WAD / 3_600_000
    # electricity_EUR_WAD = energy_kWh_WAD * EUR_per_kWh_WAD / 1e18
    # provider_EUR_WAD    = provider_USD_WAD * 1e18 / USD_per_EUR_WAD
    # settlement_EUR_WAD  = electricity_EUR_WAD + provider_EUR_WAD
    # Each division deliberately floors the smallest 1e-18 unit, matching Solidity semantics.
    if provider_cost_usd_wad < 0 or usd_per_eur_wad <= 0:
        raise ValueError("Provider cost must be non-negative and FX rate positive")
    energy_joules_wad = (
        prompt_tokens * tariff.prompt_joules_per_token_wad
        + completion_tokens * tariff.completion_joules_per_token_wad
    )
    energy_kwh_wad = energy_joules_wad // JOULES_PER_KWH
    electricity_cost_euro_wad = energy_kwh_wad * tariff.euro_per_kwh_wad // WAD
    provider_cost_euro_wad = provider_cost_usd_wad * WAD // usd_per_eur_wad
    settlement_euro_wad = electricity_cost_euro_wad + provider_cost_euro_wad
    response_text = _response_text(response)
    usage_timestamp = int(time.time()) if measured_at is None else measured_at
    if usage_timestamp < 0:
        raise ValueError("measured_at cannot be negative")

    return UsageMeasurement(
        request_id=str(_field(response, "id", "")),
        model=str(_field(response, "model", requested_model)),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        energy_joules_wad=energy_joules_wad,
        energy_kwh_wad=energy_kwh_wad,
        euro_per_kwh_wad=tariff.euro_per_kwh_wad,
        electricity_cost_euro_wad=electricity_cost_euro_wad,
        provider_cost_usd_wad=provider_cost_usd_wad,
        usd_per_eur_wad=usd_per_eur_wad,
        provider_cost_euro_wad=provider_cost_euro_wad,
        settlement_euro_wad=settlement_euro_wad,
        response_text_sha256=hashlib.sha256(response_text.encode("utf-8")).hexdigest(),
        tariff_id_sha256=hashlib.sha256(tariff.tariff_id.encode("utf-8")).hexdigest(),
        usage_timestamp=usage_timestamp,
    )


def meter_completion(
    model: str,
    messages: Sequence[Mapping[str, str]],
    tariff: EnergyTariff,
    usd_per_eur_wad: int = WAD,
    include_provider_cost: bool = False,
    **completion_kwargs: Any,
) -> tuple[Any, UsageMeasurement]:
    """Call LiteLLM and return both its response and a deterministic measurement."""
    if not model.strip() or not messages:
        raise ValueError("model and at least one message are required")
    from litellm import completion, completion_cost

    response = completion(model=model, messages=list(messages), **completion_kwargs)
    provider_cost_usd_wad = 0
    if include_provider_cost:
        from .pricing import decimal_usd_to_wad

        provider_cost_usd_wad = decimal_usd_to_wad(completion_cost(completion_response=response))
    return response, measurement_from_response(
        response,
        tariff,
        model,
        provider_cost_usd_wad=provider_cost_usd_wad,
        usd_per_eur_wad=usd_per_eur_wad,
    )
