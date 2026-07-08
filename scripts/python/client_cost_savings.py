#!/usr/bin/env python3
"""Calculate client LLM cost savings from editable pricing assumptions.

The formulas are intentionally stable and dependency-free. Prices stay in a
separate JSON input file so provider pricing changes do not require code edits.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any


MILLION = Decimal("1000000")
ONE = Decimal("1")
SHARE_TOLERANCE = Decimal("0.0001")
MONEY_PLACES = Decimal("0.01")
PERCENT_PLACES = Decimal("0.01")


def as_decimal(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric, got {value!r}") from exc


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def percent(value: Decimal) -> Decimal:
    return value.quantize(PERCENT_PLACES, rounding=ROUND_HALF_UP)


def to_json_number(value: Decimal, *, places: Decimal = MONEY_PLACES) -> float:
    return float(value.quantize(places, rounding=ROUND_HALF_UP))


def token_cost(
    input_tokens: Decimal,
    output_tokens: Decimal,
    input_price_per_1m: Decimal,
    output_price_per_1m: Decimal,
) -> Decimal:
    return (
        (input_tokens / MILLION * input_price_per_1m)
        + (output_tokens / MILLION * output_price_per_1m)
    )


def require_mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def calculate_savings(config: dict[str, Any]) -> dict[str, Any]:
    currency = str(config.get("currency", "EUR"))
    period = require_mapping(config, "period")
    tokens = require_mapping(config, "tokens")
    baseline = require_mapping(config, "baseline")

    users = as_decimal(period.get("users", 0), "period.users")
    requests_per_user_per_day = as_decimal(
        period.get("requests_per_user_per_day", 0),
        "period.requests_per_user_per_day",
    )
    working_days_per_month = as_decimal(
        period.get("working_days_per_month", 0),
        "period.working_days_per_month",
    )
    input_per_request = as_decimal(
        tokens.get("input_per_request", 0),
        "tokens.input_per_request",
    )
    output_per_request = as_decimal(
        tokens.get("output_per_request", 0),
        "tokens.output_per_request",
    )

    monthly_requests = users * requests_per_user_per_day * working_days_per_month
    monthly_input_tokens = monthly_requests * input_per_request
    monthly_output_tokens = monthly_requests * output_per_request

    baseline_input_price = as_decimal(
        baseline.get("input_price_per_1m", 0),
        "baseline.input_price_per_1m",
    )
    baseline_output_price = as_decimal(
        baseline.get("output_price_per_1m", 0),
        "baseline.output_price_per_1m",
    )
    baseline_provider_cost = token_cost(
        monthly_input_tokens,
        monthly_output_tokens,
        baseline_input_price,
        baseline_output_price,
    )

    routes = config.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("routes must be a non-empty array")

    share_sum = sum(as_decimal(route.get("share", 0), "routes[].share") for route in routes)
    if abs(share_sum - ONE) > SHARE_TOLERANCE:
        raise ValueError(f"route shares must sum to 1.0, got {share_sum}")

    route_results: list[dict[str, Any]] = []
    pilot_provider_cost = Decimal("0")
    for route in routes:
        if not isinstance(route, dict):
            raise ValueError("each route must be an object")
        name = str(route.get("name", "unnamed-route"))
        share = as_decimal(route.get("share", 0), f"routes[{name}].share")
        input_price = as_decimal(
            route.get("input_price_per_1m", 0),
            f"routes[{name}].input_price_per_1m",
        )
        output_price = as_decimal(
            route.get("output_price_per_1m", 0),
            f"routes[{name}].output_price_per_1m",
        )
        route_input_tokens = monthly_input_tokens * share
        route_output_tokens = monthly_output_tokens * share
        cost = token_cost(route_input_tokens, route_output_tokens, input_price, output_price)
        pilot_provider_cost += cost
        route_results.append(
            {
                "name": name,
                "share_percent": to_json_number(share * Decimal("100"), places=PERCENT_PLACES),
                "input_price_per_1m": to_json_number(input_price),
                "output_price_per_1m": to_json_number(output_price),
                "monthly_input_tokens": int(route_input_tokens),
                "monthly_output_tokens": int(route_output_tokens),
                "monthly_cost": to_json_number(cost),
            }
        )

    fixed_cost_results: list[dict[str, Any]] = []
    fixed_monthly_cost = Decimal("0")
    for fixed_cost in config.get("fixed_monthly_costs", []):
        if not isinstance(fixed_cost, dict):
            raise ValueError("each fixed monthly cost must be an object")
        name = str(fixed_cost.get("name", "fixed-cost"))
        amount = as_decimal(fixed_cost.get("amount", 0), f"fixed_monthly_costs[{name}].amount")
        fixed_monthly_cost += amount
        fixed_cost_results.append({"name": name, "amount": to_json_number(amount)})

    pilot_total_cost = pilot_provider_cost + fixed_monthly_cost
    net_savings = baseline_provider_cost - pilot_total_cost
    savings_rate = (
        net_savings / baseline_provider_cost * Decimal("100")
        if baseline_provider_cost
        else Decimal("0")
    )

    rate_limits = config.get("rate_limits", {})
    if rate_limits is None:
        rate_limits = {}
    if not isinstance(rate_limits, dict):
        raise ValueError("rate_limits must be an object")
    baseline_429_count = as_decimal(rate_limits.get("baseline_429_count", 0), "rate_limits.baseline_429_count")
    pilot_429_count = as_decimal(rate_limits.get("pilot_429_count", 0), "rate_limits.pilot_429_count")
    avoided_429_count = baseline_429_count - pilot_429_count
    baseline_429_rate = (
        baseline_429_count / monthly_requests * Decimal("100")
        if monthly_requests
        else Decimal("0")
    )
    pilot_429_rate = (
        pilot_429_count / monthly_requests * Decimal("100")
        if monthly_requests
        else Decimal("0")
    )

    return {
        "currency": currency,
        "pricing_date": config.get("pricing_date", "unknown"),
        "summary": {
            "monthly_requests": int(monthly_requests),
            "monthly_input_tokens": int(monthly_input_tokens),
            "monthly_output_tokens": int(monthly_output_tokens),
            "baseline_provider_cost": to_json_number(baseline_provider_cost),
            "pilot_provider_cost": to_json_number(pilot_provider_cost),
            "fixed_monthly_cost": to_json_number(fixed_monthly_cost),
            "pilot_total_cost": to_json_number(pilot_total_cost),
            "net_savings": to_json_number(net_savings),
            "savings_rate_percent": to_json_number(savings_rate, places=PERCENT_PLACES),
        },
        "baseline": {
            "model": baseline.get("model", "baseline"),
            "input_price_per_1m": to_json_number(baseline_input_price),
            "output_price_per_1m": to_json_number(baseline_output_price),
        },
        "routes": route_results,
        "fixed_monthly_costs": fixed_cost_results,
        "rate_limits": {
            "baseline_429_count": int(baseline_429_count),
            "pilot_429_count": int(pilot_429_count),
            "avoided_429_count": int(avoided_429_count),
            "baseline_429_rate_percent": to_json_number(baseline_429_rate, places=PERCENT_PLACES),
            "pilot_429_rate_percent": to_json_number(pilot_429_rate, places=PERCENT_PLACES),
        },
    }


def format_currency(value: float, currency: str) -> str:
    return f"{currency} {value:,.2f}"


def format_markdown(result: dict[str, Any]) -> str:
    currency = result["currency"]
    summary = result["summary"]
    rate_limits = result["rate_limits"]
    lines = [
        "# Client LLM Cost Savings",
        "",
        f"- Pricing date: {result['pricing_date']}",
        f"- Monthly requests: {summary['monthly_requests']:,}",
        f"- Baseline provider cost: {format_currency(summary['baseline_provider_cost'], currency)}",
        f"- Pilot provider cost: {format_currency(summary['pilot_provider_cost'], currency)}",
        f"- Fixed monthly cost: {format_currency(summary['fixed_monthly_cost'], currency)}",
        f"- Pilot total cost: {format_currency(summary['pilot_total_cost'], currency)}",
        f"- Net monthly savings: {format_currency(summary['net_savings'], currency)}",
        f"- Savings rate: {summary['savings_rate_percent']:.2f}%",
        f"- Avoided 429 errors: {rate_limits['avoided_429_count']:,}",
        "",
        "## Routing Mix",
        "",
        "| Route | Share | Input price / 1M | Output price / 1M | Monthly cost |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for route in result["routes"]:
        lines.append(
            "| {name} | {share:.2f}% | {input_price} | {output_price} | {cost} |".format(
                name=route["name"],
                share=route["share_percent"],
                input_price=format_currency(route["input_price_per_1m"], currency),
                output_price=format_currency(route["output_price_per_1m"], currency),
                cost=format_currency(route["monthly_cost"], currency),
            )
        )
    lines.extend(
        [
            "",
            "## Fixed Monthly Costs",
            "",
            "| Cost | Amount |",
            "| --- | ---: |",
        ]
    )
    for fixed_cost in result["fixed_monthly_costs"]:
        lines.append(
            f"| {fixed_cost['name']} | {format_currency(fixed_cost['amount'], currency)} |"
        )
    return "\n".join(lines) + "\n"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("input file must contain a JSON object")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calculate client LLM cost savings from a JSON assumptions file.",
    )
    parser.add_argument("--input", required=True, type=Path, help="Path to assumptions JSON.")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format.",
    )
    parser.add_argument("--output", type=Path, help="Optional output file path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = calculate_savings(load_config(args.input))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.format == "markdown":
        rendered = format_markdown(result)
    else:
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"

    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
