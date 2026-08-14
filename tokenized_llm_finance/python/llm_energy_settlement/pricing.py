"""Market-backed electricity and FX pricing with bounded automatic adjustments."""

from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol

from .metering import WAD, decimal_to_wad

ENTSOE_API_URL = "https://web-api.tp.entsoe.eu/api"
ECB_DAILY_FX_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
FRANCE_BIDDING_ZONE = "10YFR-RTE------C"
MAX_MARKET_RESPONSE_BYTES = 5_000_000


class UrlReader(Protocol):
    def __call__(self, url: str, timeout: float) -> bytes: ...


def _read_url(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "llm-energy-settlement/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        if response.status != 200:
            raise ConnectionError(f"Market data endpoint returned HTTP {response.status}")
        payload = response.read(MAX_MARKET_RESPONSE_BYTES + 1)
        if len(payload) > MAX_MARKET_RESPONSE_BYTES:
            raise ValueError("Market data response exceeds the configured size limit")
        return payload


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str:
    for child in element:
        if _local_name(child.tag) == name and child.text:
            return child.text.strip()
    raise ValueError(f"Missing XML field: {name}")


def _parse_decimal(value: str, field_name: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal market field {field_name}: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"Non-finite market field: {field_name}")
    return result


@dataclass(frozen=True, slots=True)
class PriceQuote:
    value_wad: int
    observed_at: int
    source: str

    def __post_init__(self) -> None:
        # Electricity spot markets can legitimately publish negative prices. The
        # adjustment policy applies the configured retail/settlement floor later.
        if self.observed_at < 0 or not self.source.strip():
            raise ValueError("Invalid market quote")


@dataclass(frozen=True, slots=True)
class PricingSnapshot:
    electricity_euro_per_kwh_wad: int
    usd_per_eur_wad: int
    electricity_observed_at: int
    fx_observed_at: int
    electricity_source: str
    fx_source: str
    generated_at: int

    def __post_init__(self) -> None:
        if self.electricity_euro_per_kwh_wad < 0 or self.usd_per_eur_wad <= 0:
            raise ValueError("Invalid accepted market values")
        if min(self.electricity_observed_at, self.fx_observed_at, self.generated_at) < 0:
            raise ValueError("Invalid market timestamps")
        if not self.electricity_source.strip() or not self.fx_source.strip():
            raise ValueError("Market sources are required")

    @property
    def tariff_id(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        import hashlib

        return f"market-v1-{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


class EntsoeDayAheadClient:
    """Read the current bidding-zone day-ahead EUR/MWh point from ENTSO-E."""

    def __init__(
        self,
        api_token: str,
        bidding_zone: str = FRANCE_BIDDING_ZONE,
        *,
        timeout_seconds: float = 15,
        reader: UrlReader = _read_url,
    ) -> None:
        if not api_token.strip() or not bidding_zone.strip() or timeout_seconds <= 0:
            raise ValueError("ENTSO-E token, bidding zone and positive timeout are required")
        self._api_token = api_token
        self._bidding_zone = bidding_zone
        self._timeout_seconds = timeout_seconds
        self._reader = reader

    def electricity_euro_per_kwh(self, now: datetime | None = None) -> PriceQuote:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        start = current - timedelta(days=2)
        end = current + timedelta(days=2)
        query = urllib.parse.urlencode(
            {
                "securityToken": self._api_token,
                "documentType": "A44",
                "in_Domain": self._bidding_zone,
                "out_Domain": self._bidding_zone,
                "periodStart": start.strftime("%Y%m%d%H%M"),
                "periodEnd": end.strftime("%Y%m%d%H%M"),
            }
        )
        payload = self._reader(f"{ENTSOE_API_URL}?{query}", self._timeout_seconds)
        return self._parse_price(payload, current)

    @staticmethod
    def _parse_price(payload: bytes, current: datetime) -> PriceQuote:
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise ValueError("ENTSO-E returned malformed XML") from exc
        if _local_name(root.tag) == "Acknowledgement_MarketDocument":
            reasons = [
                element.text.strip()
                for element in root.iter()
                if _local_name(element.tag) == "text" and element.text
            ]
            raise ValueError(
                f"ENTSO-E rejected the query: {'; '.join(reasons) or 'unknown reason'}"
            )

        candidates: list[tuple[datetime, Decimal]] = []
        for period in (element for element in root.iter() if _local_name(element.tag) == "Period"):
            interval = next(
                (child for child in period if _local_name(child.tag) == "timeInterval"), None
            )
            if interval is None:
                continue
            start_text = _child_text(interval, "start")
            period_start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
            resolution = _child_text(period, "resolution")
            seconds = {"PT15M": 900, "PT30M": 1800, "PT60M": 3600}.get(resolution)
            if seconds is None:
                raise ValueError(f"Unsupported ENTSO-E resolution: {resolution}")
            for point in (child for child in period if _local_name(child.tag) == "Point"):
                position = int(_child_text(point, "position"))
                price_mwh = _parse_decimal(_child_text(point, "price.amount"), "price.amount")
                point_time = period_start + timedelta(seconds=(position - 1) * seconds)
                if point_time <= current < point_time + timedelta(seconds=seconds):
                    candidates.append((point_time, price_mwh))

        if not candidates:
            raise ValueError("ENTSO-E response has no price covering the current time")
        observed_at, price_mwh = max(candidates, key=lambda item: item[0])
        # ENTSO-E publishes EUR/MWh. 1 MWh = 1,000 kWh.
        price_kwh = price_mwh / Decimal(1000)
        return PriceQuote(
            value_wad=int(price_kwh * WAD),
            observed_at=int(observed_at.timestamp()),
            source="ENTSO-E:A44",
        )


class EcbFxClient:
    """Read the ECB daily USD-per-EUR reference rate."""

    def __init__(self, *, timeout_seconds: float = 15, reader: UrlReader = _read_url) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds
        self._reader = reader

    def usd_per_eur(self) -> PriceQuote:
        payload = self._reader(ECB_DAILY_FX_URL, self._timeout_seconds)
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise ValueError("ECB returned malformed XML") from exc
        dated_cube = next(
            (
                element
                for element in root.iter()
                if _local_name(element.tag) == "Cube" and element.get("time")
            ),
            None,
        )
        if dated_cube is None:
            raise ValueError("ECB response has no dated rate set")
        usd_cube = next(
            (element for element in dated_cube if element.get("currency") == "USD"), None
        )
        if usd_cube is None or not usd_cube.get("rate"):
            raise ValueError("ECB response has no USD rate")
        rate = _parse_decimal(usd_cube.attrib["rate"], "USD rate")
        if rate <= 0:
            raise ValueError("ECB USD-per-EUR rate must be positive")
        observed = datetime.fromisoformat(dated_cube.attrib["time"]).replace(tzinfo=UTC)
        return PriceQuote(
            decimal_to_wad(format(rate, "f")), int(observed.timestamp()), "ECB:USD/EUR"
        )


@dataclass(frozen=True, slots=True)
class AdjustmentPolicy:
    minimum_euro_per_kwh_wad: int
    maximum_euro_per_kwh_wad: int
    maximum_change_bps: int = 1_000
    maximum_electricity_age_seconds: int = 7_200
    maximum_fx_age_seconds: int = 345_600
    minimum_usd_per_eur_wad: int = WAD // 2
    maximum_usd_per_eur_wad: int = WAD * 2
    maximum_fx_change_bps: int = 500

    def __post_init__(self) -> None:
        if not 0 < self.minimum_euro_per_kwh_wad <= self.maximum_euro_per_kwh_wad:
            raise ValueError("Invalid electricity price bounds")
        if not 0 <= self.maximum_change_bps <= 10_000:
            raise ValueError("maximum_change_bps must be between 0 and 10000")
        if not 0 < self.minimum_usd_per_eur_wad <= self.maximum_usd_per_eur_wad:
            raise ValueError("Invalid FX rate bounds")
        if not 0 <= self.maximum_fx_change_bps <= 10_000:
            raise ValueError("maximum_fx_change_bps must be between 0 and 10000")
        if self.maximum_electricity_age_seconds <= 0 or self.maximum_fx_age_seconds <= 0:
            raise ValueError("Quote age limits must be positive")


class AdaptiveMarketPricing:
    """Validate market feeds and rate-limit changes against the last accepted snapshot."""

    def __init__(
        self, electricity: EntsoeDayAheadClient, fx: EcbFxClient, policy: AdjustmentPolicy
    ):
        self._electricity = electricity
        self._fx = fx
        self._policy = policy

    def snapshot(self, state_path: Path, now: int | None = None) -> PricingSnapshot:
        timestamp = int(time.time()) if now is None else now
        if timestamp < 0:
            raise ValueError("now cannot be negative")
        electricity = self._electricity.electricity_euro_per_kwh(
            datetime.fromtimestamp(timestamp, UTC)
        )
        fx = self._fx.usd_per_eur()
        self._check_freshness(electricity, timestamp, self._policy.maximum_electricity_age_seconds)
        self._check_freshness(fx, timestamp, self._policy.maximum_fx_age_seconds)
        if (
            not self._policy.minimum_usd_per_eur_wad
            <= fx.value_wad
            <= (self._policy.maximum_usd_per_eur_wad)
        ):
            raise ValueError("FX quote is outside configured safety bounds")

        bounded = min(
            max(electricity.value_wad, self._policy.minimum_euro_per_kwh_wad),
            self._policy.maximum_euro_per_kwh_wad,
        )
        previous = self._load_previous(state_path)
        if previous is not None:
            maximum_delta = (
                previous.electricity_euro_per_kwh_wad * self._policy.maximum_change_bps // 10_000
            )
            lower = max(
                self._policy.minimum_euro_per_kwh_wad,
                previous.electricity_euro_per_kwh_wad - maximum_delta,
            )
            upper = min(
                self._policy.maximum_euro_per_kwh_wad,
                previous.electricity_euro_per_kwh_wad + maximum_delta,
            )
            bounded = min(max(bounded, lower), upper)
            maximum_fx_delta = (
                previous.usd_per_eur_wad * self._policy.maximum_fx_change_bps // 10_000
            )
            fx_lower = max(
                self._policy.minimum_usd_per_eur_wad,
                previous.usd_per_eur_wad - maximum_fx_delta,
            )
            fx_upper = min(
                self._policy.maximum_usd_per_eur_wad,
                previous.usd_per_eur_wad + maximum_fx_delta,
            )
            accepted_fx_wad = min(max(fx.value_wad, fx_lower), fx_upper)
        else:
            accepted_fx_wad = fx.value_wad

        result = PricingSnapshot(
            electricity_euro_per_kwh_wad=bounded,
            usd_per_eur_wad=accepted_fx_wad,
            electricity_observed_at=electricity.observed_at,
            fx_observed_at=fx.observed_at,
            electricity_source=electricity.source,
            fx_source=fx.source,
            generated_at=timestamp,
        )
        self._store(state_path, result)
        return result

    @staticmethod
    def _check_freshness(quote: PriceQuote, now: int, maximum_age: int) -> None:
        if quote.observed_at > now + 300 or now - quote.observed_at > maximum_age:
            raise ValueError(f"Stale or future market quote from {quote.source}")

    @staticmethod
    def _load_previous(path: Path) -> PricingSnapshot | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return PricingSnapshot(**data)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid pricing state file: {path}") from exc

    @staticmethod
    def _store(path: Path, snapshot: PricingSnapshot) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(asdict(snapshot), handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise


def usd_wad_to_euro_wad(usd_wad: int, usd_per_eur_wad: int) -> int:
    """Convert USD WAD to EUR WAD: EUR = USD / (USD per EUR)."""
    if usd_wad < 0 or usd_per_eur_wad <= 0:
        raise ValueError("USD amount must be non-negative and FX rate positive")
    return usd_wad * WAD // usd_per_eur_wad


def decimal_usd_to_wad(value: object) -> int:
    """Floor an external USD estimate to WAD without binary-float arithmetic."""
    amount = _parse_decimal(str(value), "provider cost USD")
    if amount < 0:
        raise ValueError("Provider cost cannot be negative")
    return int((amount * WAD).to_integral_value(rounding=ROUND_DOWN))
