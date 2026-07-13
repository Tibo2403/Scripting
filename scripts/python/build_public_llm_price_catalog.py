#!/usr/bin/env python3
"""Build a normalized API-price catalog from LiteLLM's public cost map."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)


def fetch_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "Scripting-cost-catalog/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - explicit user URL
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("source root must be an object")
    return value


def normalize(source: dict[str, Any], source_url: str, fetched_at: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    providers: set[str] = set()
    for model, details in source.items():
        if model == "sample_spec" or not isinstance(details, dict):
            continue
        mode = details.get("mode")
        input_cost = details.get("input_cost_per_token")
        output_cost = details.get("output_cost_per_token")
        if mode not in {"chat", "completion"} or not isinstance(input_cost, (int, float)):
            continue
        if not isinstance(output_cost, (int, float)):
            continue
        provider = str(details.get("litellm_provider", "unknown"))
        providers.add(provider)
        entry = {
            "id": f"api:{model}",
            "name": model,
            "type": "api",
            "currency": "USD",
            "provider": provider,
            "litellm_model": model,
            "input_price_per_1m": input_cost * 1_000_000,
            "output_price_per_1m": output_cost * 1_000_000,
            "source_url": details.get("source", source_url),
            "source_kind": "public-aggregator",
            "fetched_at": fetched_at,
        }
        for field in ("max_input_tokens", "max_output_tokens", "supports_function_calling"):
            if field in details:
                entry[field] = details[field]
        entries.append(entry)
    entries.sort(key=lambda item: item["id"])
    return {
        "schema_version": 1,
        "generated_at": fetched_at,
        "source": {
            "name": "LiteLLM model cost map",
            "url": source_url,
            "warning": "Aggregator snapshot; verify finalists against the provider's official pricing page.",
        },
        "statistics": {"api_models": len(entries), "providers": len(providers)},
        "entries": entries,
    }


def merge_base_catalog(catalog: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    base_entries = base.get("entries") if isinstance(base, dict) else None
    if not isinstance(base_entries, list):
        raise ValueError("base catalog entries must be an array")
    entries = catalog["entries"]
    known_ids = {entry["id"] for entry in entries}
    for entry in base_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("each base catalog entry must have a string id")
        if entry["id"] in known_ids:
            raise ValueError(f"duplicate catalog id: {entry['id']}")
        entries.append(entry)
        known_ids.add(entry["id"])
    entries.sort(key=lambda item: item["id"])
    catalog["statistics"]["compute_offers"] = len(base_entries)
    catalog["additional_sources"] = base.get("sources", [])
    catalog["reference_only"] = base.get("reference_only", [])
    return catalog


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", default=DEFAULT_URL)
    parser.add_argument("--source-file", type=Path, help="offline LiteLLM map fixture")
    parser.add_argument("--base-catalog", type=Path, help="append normalized compute entries")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        source = (
            json.loads(args.source_file.read_text(encoding="utf-8"))
            if args.source_file
            else fetch_json(args.source_url)
        )
        if not isinstance(source, dict):
            raise ValueError("source root must be an object")
        fetched_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        catalog = normalize(source, args.source_url, fetched_at)
        if args.base_catalog:
            base = json.loads(args.base_catalog.read_text(encoding="utf-8"))
            catalog = merge_base_catalog(catalog, base)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        stats = catalog["statistics"]
        compute = stats.get("compute_offers", 0)
        print(
            f"wrote {stats['api_models']} API models from {stats['providers']} providers "
            f"and {compute} compute offers to {args.output}"
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError, URLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
