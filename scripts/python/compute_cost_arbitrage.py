#!/usr/bin/env python3
"""Compare self-hosted, rented compute, and LLM API costs.

Pricing and quality scores are deliberately supplied through JSON. This keeps
the formulas reproducible while cloud, electricity, and API prices change.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any


MILLION = Decimal("1000000")
SECONDS_PER_HOUR = Decimal("3600")
MONEY_PLACES = Decimal("0.01")
DETAIL_PLACES = Decimal("0.0001")
HISTORY_FIELDS = (
    "observed_at",
    "pricing_date",
    "currency",
    "candidate",
    "option_type",
    "eligible",
    "selected_primary",
    "monthly_cost",
    "cost_per_1m_tokens",
    "quality_score",
    "quality_margin",
    "litellm_model",
    "hourly_price",
    "electricity_price_per_kwh",
    "energy_kwh",
)
TREND_FIELDS = (
    "period",
    "period_start",
    "period_end",
    "currency",
    "candidate",
    "option_type",
    "observations",
    "eligible_rate_pct",
    "selected_primary_count",
    "average_monthly_cost",
    "minimum_monthly_cost",
    "maximum_monthly_cost",
    "change_from_previous_period",
    "change_pct_from_previous_period",
    "average_cost_per_1m_tokens",
    "average_hourly_price",
    "average_electricity_price_per_kwh",
    "average_energy_kwh",
)


def decimal_value(value: Any, field: str, *, minimum: Decimal = Decimal("0")) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be numeric, got {value!r}") from exc
    if result < minimum:
        raise ValueError(f"{field} must be >= {minimum}, got {result}")
    return result


def rounded(value: Decimal, places: Decimal = MONEY_PLACES) -> float:
    return float(value.quantize(places, rounding=ROUND_HALF_UP))


def mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    """Load a normalized public-price catalog indexed by stable id."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("entries") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        raise ValueError("catalog.entries must be an array")
    indexed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("each catalog entry must have a string id")
        indexed[entry["id"]] = entry
    return indexed


def expand_catalog_options(
    config: dict[str, Any], catalog: dict[str, dict[str, Any]] | None
) -> dict[str, Any]:
    """Merge catalog pricing with scenario-specific quality/capacity measurements."""
    refs = config.get("catalog_options", [])
    if not refs:
        return config
    if catalog is None:
        raise ValueError("catalog_options requires --catalog")
    if not isinstance(refs, list):
        raise ValueError("catalog_options must be an array")
    expanded = deepcopy(config)
    options = expanded.setdefault("options", [])
    if not isinstance(options, list):
        raise ValueError("options must be an array")
    target_currency = str(config.get("currency", "USD"))
    conversions = config.get("currency_conversion", {})
    if not isinstance(conversions, dict):
        raise ValueError("currency_conversion must be an object")
    price_fields = ("input_price_per_1m", "output_price_per_1m", "hourly_price")
    for ref in refs:
        if not isinstance(ref, dict) or not isinstance(ref.get("catalog_id"), str):
            raise ValueError("each catalog option must have a string catalog_id")
        catalog_id = ref["catalog_id"]
        if catalog_id not in catalog:
            raise ValueError(f"catalog entry not found: {catalog_id}")
        option = deepcopy(catalog[catalog_id])
        source_currency = str(option.get("currency", target_currency))
        if source_currency != target_currency:
            if source_currency not in conversions:
                raise ValueError(
                    f"currency_conversion.{source_currency} is required to convert "
                    f"{catalog_id} to {target_currency}"
                )
            rate = decimal_value(conversions[source_currency], f"currency_conversion.{source_currency}")
            for field in price_fields:
                if field in option:
                    option[field] = str(decimal_value(option[field], field) * rate)
        option.update({key: value for key, value in ref.items() if key != "catalog_id"})
        option["catalog_id"] = catalog_id
        options.append(option)
    return expanded


def quality(option: dict[str, Any], name: str) -> Decimal:
    score = decimal_value(option.get("quality_score", 0), f"options[{name}].quality_score")
    if score > 100:
        raise ValueError(f"options[{name}].quality_score must be <= 100")
    return score


def token_hours(total_tokens: Decimal, tokens_per_second: Decimal) -> Decimal:
    if tokens_per_second == 0:
        raise ValueError("tokens_per_second must be greater than zero")
    return total_tokens / tokens_per_second / SECONDS_PER_HOUR


def self_hosted_result(
    option: dict[str, Any],
    *,
    total_tokens: Decimal,
    minimum_quality: Decimal,
    tariff_name: str,
    price_per_kwh: Decimal,
) -> dict[str, Any]:
    name = str(option.get("name", "self-hosted"))
    score = quality(option, name)
    throughput = decimal_value(option.get("tokens_per_second", 0), f"options[{name}].tokens_per_second")
    required_hours = token_hours(total_tokens, throughput)
    online_hours = decimal_value(option.get("online_hours_per_month", 0), f"options[{name}].online_hours_per_month")
    load_hours = min(required_hours, online_hours)
    idle_hours = max(online_hours - load_hours, Decimal("0"))
    load_watts = decimal_value(option.get("load_power_watts", 0), f"options[{name}].load_power_watts")
    idle_watts = decimal_value(option.get("idle_power_watts", 0), f"options[{name}].idle_power_watts")
    pue = decimal_value(option.get("pue", 1), f"options[{name}].pue")
    if pue < 1:
        raise ValueError(f"options[{name}].pue must be >= 1")
    energy_kwh = ((load_hours * load_watts) + (idle_hours * idle_watts)) / Decimal("1000") * pue
    energy_cost = energy_kwh * price_per_kwh

    hardware_cost = decimal_value(option.get("hardware_cost", 0), f"options[{name}].hardware_cost")
    residual_value = decimal_value(option.get("residual_value", 0), f"options[{name}].residual_value")
    if residual_value > hardware_cost:
        raise ValueError(f"options[{name}].residual_value cannot exceed hardware_cost")
    amortization_months = decimal_value(option.get("amortization_months", 1), f"options[{name}].amortization_months")
    if amortization_months == 0:
        raise ValueError(f"options[{name}].amortization_months must be greater than zero")
    amortization = (hardware_cost - residual_value) / amortization_months
    fixed_cost = decimal_value(option.get("fixed_monthly_cost", 0), f"options[{name}].fixed_monthly_cost")
    non_energy_cost = amortization + fixed_cost
    monthly_cost = non_energy_cost + energy_cost
    capacity_ok = required_hours <= online_hours
    quality_ok = score >= minimum_quality

    return {
        "name": name,
        "candidate": f"{name} @ {tariff_name}",
        "type": "self_hosted",
        "litellm_model": option.get("litellm_model"),
        "quality_score": rounded(score),
        "quality_margin": rounded(score - minimum_quality),
        "quality_ok": quality_ok,
        "capacity_ok": capacity_ok,
        "eligible": quality_ok and capacity_ok,
        "monthly_cost": rounded(monthly_cost),
        "cost_per_1m_tokens": rounded(monthly_cost / total_tokens * MILLION),
        "required_inference_hours": rounded(required_hours),
        "available_hours": rounded(online_hours),
        "energy_kwh": rounded(energy_kwh),
        "electricity_tariff": tariff_name,
        "electricity_price_per_kwh": rounded(price_per_kwh, DETAIL_PLACES),
        "electricity_cost": rounded(energy_cost),
        "amortization_cost": rounded(amortization),
        "fixed_monthly_cost": rounded(fixed_cost),
        "non_energy_cost": rounded(non_energy_cost),
    }


def rented_compute_result(
    option: dict[str, Any],
    *,
    total_tokens: Decimal,
    minimum_quality: Decimal,
) -> dict[str, Any]:
    name = str(option.get("name", "rented-compute"))
    score = quality(option, name)
    throughput = decimal_value(option.get("tokens_per_second", 0), f"options[{name}].tokens_per_second")
    required_hours = token_hours(total_tokens, throughput)
    billed_hours = decimal_value(option.get("billed_hours_per_month", 0), f"options[{name}].billed_hours_per_month")
    hourly_price = decimal_value(option.get("hourly_price", 0), f"options[{name}].hourly_price")
    fixed_cost = decimal_value(option.get("fixed_monthly_cost", 0), f"options[{name}].fixed_monthly_cost")
    monthly_cost = billed_hours * hourly_price + fixed_cost
    capacity_ok = required_hours <= billed_hours
    quality_ok = score >= minimum_quality
    return {
        "name": name,
        "candidate": name,
        "type": "rented_compute",
        "litellm_model": option.get("litellm_model"),
        "quality_score": rounded(score),
        "quality_margin": rounded(score - minimum_quality),
        "quality_ok": quality_ok,
        "capacity_ok": capacity_ok,
        "eligible": quality_ok and capacity_ok,
        "monthly_cost": rounded(monthly_cost),
        "cost_per_1m_tokens": rounded(monthly_cost / total_tokens * MILLION),
        "required_inference_hours": rounded(required_hours),
        "available_hours": rounded(billed_hours),
        "hourly_price": rounded(hourly_price, DETAIL_PLACES),
        "fixed_monthly_cost": rounded(fixed_cost),
    }


def api_result(
    option: dict[str, Any],
    *,
    input_tokens: Decimal,
    output_tokens: Decimal,
    total_tokens: Decimal,
    minimum_quality: Decimal,
) -> dict[str, Any]:
    name = str(option.get("name", "llm-api"))
    score = quality(option, name)
    input_price = decimal_value(option.get("input_price_per_1m", 0), f"options[{name}].input_price_per_1m")
    output_price = decimal_value(option.get("output_price_per_1m", 0), f"options[{name}].output_price_per_1m")
    fixed_cost = decimal_value(option.get("fixed_monthly_cost", 0), f"options[{name}].fixed_monthly_cost")
    monthly_cost = input_tokens / MILLION * input_price + output_tokens / MILLION * output_price + fixed_cost
    quality_ok = score >= minimum_quality
    return {
        "name": name,
        "candidate": name,
        "type": "api",
        "litellm_model": option.get("litellm_model"),
        "quality_score": rounded(score),
        "quality_margin": rounded(score - minimum_quality),
        "quality_ok": quality_ok,
        "capacity_ok": True,
        "eligible": quality_ok,
        "monthly_cost": rounded(monthly_cost),
        "cost_per_1m_tokens": rounded(monthly_cost / total_tokens * MILLION),
        "input_price_per_1m": rounded(input_price, DETAIL_PLACES),
        "output_price_per_1m": rounded(output_price, DETAIL_PLACES),
        "fixed_monthly_cost": rounded(fixed_cost),
    }


def analyze(
    config: dict[str, Any],
    *,
    minimum_quality_override: Decimal | None = None,
    electricity_price_override: Decimal | None = None,
    catalog: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    config = expand_catalog_options(config, catalog)
    workload = mapping(config, "workload")
    input_tokens = decimal_value(workload.get("monthly_input_tokens", 0), "workload.monthly_input_tokens")
    output_tokens = decimal_value(workload.get("monthly_output_tokens", 0), "workload.monthly_output_tokens")
    total_tokens = input_tokens + output_tokens
    if total_tokens == 0:
        raise ValueError("monthly token volume must be greater than zero")
    minimum_quality = (
        decimal_value(minimum_quality_override, "minimum quality override")
        if minimum_quality_override is not None
        else decimal_value(workload.get("minimum_quality_score", 0), "workload.minimum_quality_score")
    )
    if minimum_quality > 100:
        raise ValueError("minimum quality score must be <= 100")

    raw_tariffs = config.get("electricity_tariffs", [])
    if not isinstance(raw_tariffs, list) or not raw_tariffs:
        raise ValueError("electricity_tariffs must be a non-empty array")
    if electricity_price_override is not None:
        tariffs = [("CLI override", decimal_value(electricity_price_override, "electricity price override"))]
    else:
        tariffs = []
        for item in raw_tariffs:
            if not isinstance(item, dict):
                raise ValueError("each electricity tariff must be an object")
            name = str(item.get("name", "tariff"))
            tariffs.append((name, decimal_value(item.get("price_per_kwh", 0), f"electricity_tariffs[{name}].price_per_kwh")))

    options = config.get("options")
    if not isinstance(options, list) or not options:
        raise ValueError("options must be a non-empty array")
    results: list[dict[str, Any]] = []
    for option in options:
        if not isinstance(option, dict):
            raise ValueError("each option must be an object")
        option_type = option.get("type")
        if option_type == "self_hosted":
            for tariff_name, tariff_price in tariffs:
                results.append(self_hosted_result(option, total_tokens=total_tokens, minimum_quality=minimum_quality, tariff_name=tariff_name, price_per_kwh=tariff_price))
        elif option_type == "rented_compute":
            results.append(rented_compute_result(option, total_tokens=total_tokens, minimum_quality=minimum_quality))
        elif option_type == "api":
            results.append(api_result(option, input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens, minimum_quality=minimum_quality))
        else:
            raise ValueError(f"unsupported option type: {option_type!r}")

    ranked = sorted((item for item in results if item["eligible"]), key=lambda item: item["monthly_cost"])
    primary = ranked[0] if ranked else None
    fallback = ranked[1] if len(ranked) > 1 else None
    best_api = next((item for item in ranked if item["type"] == "api"), None)

    break_even: list[dict[str, Any]] = []
    if best_api:
        seen: set[str] = set()
        for item in results:
            if item["type"] != "self_hosted" or item["name"] in seen:
                continue
            seen.add(item["name"])
            energy_kwh = Decimal(str(item["energy_kwh"]))
            non_energy = Decimal(str(item["non_energy_cost"]))
            api_cost = Decimal(str(best_api["monthly_cost"]))
            threshold = (api_cost - non_energy) / energy_kwh if energy_kwh else Decimal("0")
            break_even.append({
                "self_hosted": item["name"],
                "compared_api": best_api["name"],
                "max_price_per_kwh": rounded(threshold, DETAIL_PLACES),
                "interpretation": "self-hosting remains cheaper below this electricity price" if threshold >= 0 else "API is cheaper even with free electricity",
            })

    return {
        "currency": str(config.get("currency", "EUR")),
        "pricing_date": config.get("pricing_date", "user-maintained"),
        "workload": {
            "monthly_input_tokens": int(input_tokens),
            "monthly_output_tokens": int(output_tokens),
            "monthly_total_tokens": int(total_tokens),
            "minimum_quality_score": rounded(minimum_quality),
        },
        "recommendation": {
            "primary": primary["candidate"] if primary else None,
            "primary_litellm_model": primary.get("litellm_model") if primary else None,
            "fallback": fallback["candidate"] if fallback else None,
            "fallback_litellm_model": fallback.get("litellm_model") if fallback else None,
            "monthly_cost": primary["monthly_cost"] if primary else None,
        },
        "candidates": sorted(results, key=lambda item: (not item["eligible"], item["monthly_cost"])),
        "electricity_break_even": break_even,
    }


def currency(value: float, code: str) -> str:
    return f"{code} {value:,.2f}"


def format_markdown(result: dict[str, Any]) -> str:
    code = result["currency"]
    recommendation = result["recommendation"]
    lines = [
        "# Compute / LLM API Cost Arbitrage",
        "",
        f"- Pricing date: {result['pricing_date']}",
        f"- Minimum quality: {result['workload']['minimum_quality_score']:.2f}/100",
        f"- Primary: {recommendation['primary'] or 'none'}",
        f"- LiteLLM model: {recommendation['primary_litellm_model'] or 'not configured'}",
        f"- Estimated monthly cost: {currency(recommendation['monthly_cost'], code) if recommendation['monthly_cost'] is not None else 'n/a'}",
        "",
        "## Candidates",
        "",
        "| Candidate | Type | Quality | Margin | Eligible | Monthly cost | Cost / 1M tokens | kWh |",
        "| --- | --- | ---: | ---: | :---: | ---: | ---: | ---: |",
    ]
    for item in result["candidates"]:
        lines.append(
            "| {candidate} | {type} | {quality:.2f} | {margin:.2f} | {eligible} | {monthly} | {per_million} | {kwh} |".format(
                candidate=item["candidate"], type=item["type"], quality=item["quality_score"],
                margin=item["quality_margin"], eligible="yes" if item["eligible"] else "no",
                monthly=currency(item["monthly_cost"], code), per_million=currency(item["cost_per_1m_tokens"], code),
                kwh=f"{item.get('energy_kwh', 0):.2f}",
            )
        )
    lines.extend(["", "## Electricity break-even", ""])
    if result["electricity_break_even"]:
        for item in result["electricity_break_even"]:
            lines.append(
                f"- {item['self_hosted']} vs {item['compared_api']}: "
                f"{code} {item['max_price_per_kwh']:.4f}/kWh - "
                f"{item['interpretation']}."
            )
    else:
        lines.append("- No quality-eligible API comparison is available.")
    return "\n".join(lines) + "\n"


def observation_time(value: str | None = None) -> datetime:
    """Return a timezone-aware UTC timestamp for a price observation."""
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def history_rows(result: dict[str, Any], observed_at: datetime) -> list[dict[str, Any]]:
    """Flatten one arbitration report into auditable candidate observations."""
    primary = result["recommendation"]["primary"]
    timestamp = observed_at.isoformat(timespec="seconds").replace("+00:00", "Z")
    rows = []
    for item in result["candidates"]:
        rows.append(
            {
                "observed_at": timestamp,
                "pricing_date": result["pricing_date"],
                "currency": result["currency"],
                "candidate": item["candidate"],
                "option_type": item["type"],
                "eligible": str(bool(item["eligible"])).lower(),
                "selected_primary": str(item["candidate"] == primary).lower(),
                "monthly_cost": item["monthly_cost"],
                "cost_per_1m_tokens": item["cost_per_1m_tokens"],
                "quality_score": item["quality_score"],
                "quality_margin": item["quality_margin"],
                "litellm_model": item.get("litellm_model") or "",
                "hourly_price": item.get("hourly_price", ""),
                "electricity_price_per_kwh": item.get("electricity_price_per_kwh", ""),
                "energy_kwh": item.get("energy_kwh", ""),
            }
        )
    return rows


def append_history(path: Path, rows: list[dict[str, Any]]) -> None:
    """Append candidate observations, creating a stable CSV header when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0
    if not needs_header:
        with path.open(encoding="utf-8", newline="") as handle:
            existing_header = next(csv.reader(handle), [])
        if existing_header != list(HISTORY_FIELDS):
            raise ValueError("history CSV header does not match the supported format")
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_FIELDS, extrasaction="ignore")
        if needs_header:
            writer.writeheader()
        writer.writerows(rows)


def read_history(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(HISTORY_FIELDS):
            raise ValueError("history CSV header does not match the supported format")
        return list(reader)


def period_bounds(observed_at: datetime, period: str) -> tuple[str, str]:
    day = observed_at.date()
    if period == "weekly":
        start = day - timedelta(days=day.weekday())
        end = start + timedelta(days=6)
    else:
        start = end = day
    return start.isoformat(), end.isoformat()


def optional_average(rows: list[dict[str, str]], field: str) -> float | str:
    values = [Decimal(row[field]) for row in rows if row.get(field, "") != ""]
    return rounded(sum(values, Decimal("0")) / len(values), DETAIL_PLACES) if values else ""


def build_trends(history: list[dict[str, str]], periods: tuple[str, ...]) -> list[dict[str, Any]]:
    """Aggregate observations by UTC day or ISO week and calculate period changes."""
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in history:
        observed = observation_time(row["observed_at"])
        for period in periods:
            start, _ = period_bounds(observed, period)
            key = (period, start, row["currency"], row["candidate"], row["option_type"])
            grouped[key].append(row)

    summaries: list[dict[str, Any]] = []
    for (period, start, currency_code, candidate, option_type), rows in grouped.items():
        _, end = period_bounds(observation_time(rows[0]["observed_at"]), period)
        costs = [Decimal(row["monthly_cost"]) for row in rows]
        average_cost = sum(costs, Decimal("0")) / len(costs)
        summaries.append(
            {
                "period": period,
                "period_start": start,
                "period_end": end,
                "currency": currency_code,
                "candidate": candidate,
                "option_type": option_type,
                "observations": len(rows),
                "eligible_rate_pct": rounded(
                    Decimal(sum(row["eligible"].lower() == "true" for row in rows))
                    / Decimal(len(rows))
                    * Decimal("100")
                ),
                "selected_primary_count": sum(
                    row["selected_primary"].lower() == "true" for row in rows
                ),
                "average_monthly_cost": rounded(average_cost),
                "minimum_monthly_cost": rounded(min(costs)),
                "maximum_monthly_cost": rounded(max(costs)),
                "change_from_previous_period": "",
                "change_pct_from_previous_period": "",
                "average_cost_per_1m_tokens": optional_average(rows, "cost_per_1m_tokens"),
                "average_hourly_price": optional_average(rows, "hourly_price"),
                "average_electricity_price_per_kwh": optional_average(
                    rows, "electricity_price_per_kwh"
                ),
                "average_energy_kwh": optional_average(rows, "energy_kwh"),
            }
        )

    summaries.sort(
        key=lambda row: (
            row["period"], row["currency"], row["candidate"], row["option_type"], row["period_start"]
        )
    )
    previous: dict[tuple[str, str, str, str], Decimal] = {}
    for row in summaries:
        key = (row["period"], row["currency"], row["candidate"], row["option_type"])
        current = Decimal(str(row["average_monthly_cost"]))
        if key in previous:
            change = current - previous[key]
            row["change_from_previous_period"] = rounded(change)
            if previous[key] != 0:
                row["change_pct_from_previous_period"] = rounded(
                    change / previous[key] * Decimal("100")
                )
        previous[key] = current
    return summaries


def export_trends(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TREND_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="JSON scenario file")
    parser.add_argument("--catalog", type=Path, help="normalized public-price catalog JSON")
    parser.add_argument("--min-quality", type=Decimal, help="override minimum quality score")
    parser.add_argument("--electricity-price", type=Decimal, help="override price per kWh")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, help="write output to a file")
    parser.add_argument("--history-csv", type=Path, help="append candidate prices to this CSV")
    parser.add_argument("--trend-csv", type=Path, help="export daily or weekly trend recap CSV")
    parser.add_argument(
        "--trend-period", choices=("daily", "weekly", "both"), default="both",
        help="periods included in --trend-csv (default: both)",
    )
    parser.add_argument(
        "--observed-at", help="observation timestamp in ISO 8601; defaults to current UTC time"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("config root must be an object")
        catalog = load_catalog(args.catalog) if args.catalog else None
        result = analyze(
            config,
            minimum_quality_override=args.min_quality,
            electricity_price_override=args.electricity_price,
            catalog=catalog,
        )
        observed_at = observation_time(args.observed_at)
        if args.history_csv:
            append_history(args.history_csv, history_rows(result, observed_at))
        if args.trend_csv:
            if not args.history_csv:
                raise ValueError("--trend-csv requires --history-csv")
            periods = ("daily", "weekly") if args.trend_period == "both" else (args.trend_period,)
            export_trends(args.trend_csv, build_trends(read_history(args.history_csv), periods))
        rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n" if args.format == "json" else format_markdown(result)
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
