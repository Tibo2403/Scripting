"""Read-only business evidence reports for an existing Decision Ledger."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Optional


FIELDS = (
    "task_type", "provider", "model", "execution_mode", "decisions", "completed",
    "pending", "failed", "reviewed", "accepted", "review_coverage",
    "acceptance_rate", "observed_cost_usd", "cost_per_accepted_usd",
    "cost_is_partial",
)


def business_evidence(
    database: str | Path,
    *,
    task_type: Optional[str] = None,
    execution_mode: str = "live",
    quality_threshold: float = 0.8,
) -> list[dict[str, object]]:
    """Group observed costs and reviewed acceptance without mixing contexts.

    Acceptance requires success, a named non-automatic reviewer and a score
    meeting the threshold. All completed costs (including failures and unreviewed
    outputs) contribute to cost per accepted result. Missing outcomes mean costs
    are incomplete. No accepted results yields None, never zero unit cost.
    """
    if execution_mode not in {"live", "shadow", "all"}:
        raise ValueError("execution_mode must be live, shadow or all")
    if not math.isfinite(quality_threshold) or not 0 <= quality_threshold <= 1:
        raise ValueError("quality_threshold must be finite and between 0 and 1")
    conditions: list[str] = []
    params: list[object] = [quality_threshold]
    if execution_mode != "all":
        conditions.append("d.execution_mode = ?")
        params.append(execution_mode)
    if task_type is not None:
        conditions.append("d.task_type = ?")
        params.append(task_type)
    filters = "WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""
        WITH observations AS (
            SELECT d.*, o.request_id AS outcome_id, o.success, o.actual_cost_usd,
                o.quality_score,
                CASE WHEN o.quality_score IS NOT NULL
                    AND trim(o.reviewer, char(9) || char(10) || char(13) || ' ') != ''
                    AND lower(trim(o.reviewer, char(9) || char(10) || char(13) || ' '))
                        != 'automatic'
                    THEN 1 ELSE 0 END AS is_reviewed
            FROM decisions d LEFT JOIN outcomes o ON o.request_id = d.request_id
        )
        SELECT d.task_type, d.selected_provider AS provider,
            d.selected_model AS model, d.execution_mode,
            COUNT(*) AS decisions, COUNT(d.outcome_id) AS completed,
            SUM(CASE WHEN d.success = 0 THEN 1 ELSE 0 END) AS failed,
            SUM(d.is_reviewed) AS reviewed,
            SUM(CASE WHEN d.success = 1 AND d.is_reviewed = 1
                AND d.quality_score >= ? THEN 1 ELSE 0 END) AS accepted,
            COALESCE(SUM(d.actual_cost_usd), 0.0) AS observed_cost_usd
        FROM observations d
        {filters}
        GROUP BY d.task_type, d.selected_provider, d.selected_model, d.execution_mode
        ORDER BY d.task_type, d.selected_provider, d.selected_model, d.execution_mode
    """
    # mode=ro prevents typo paths from creating databases and forbids migrations.
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute(query, params)]
    for row in rows:
        completed, reviewed, accepted = row["completed"], row["reviewed"], row["accepted"]
        row["pending"] = row["decisions"] - completed
        row["review_coverage"] = reviewed / completed if completed else None
        row["acceptance_rate"] = accepted / reviewed if reviewed else None
        row["cost_per_accepted_usd"] = (
            row["observed_cost_usd"] / accepted if accepted else None
        )
        row["cost_is_partial"] = bool(row["pending"])
    return rows


def main(argv: Optional[list[str]] = None) -> int:
    """Write JSON or CSV to stdout; diagnostics go to stderr."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--task-type")
    parser.add_argument("--execution-mode", choices=("live", "shadow", "all"), default="live")
    parser.add_argument("--quality-threshold", type=float, default=0.8)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    args = parser.parse_args(argv)
    try:
        rows = business_evidence(
            args.database, task_type=args.task_type,
            execution_mode=args.execution_mode, quality_threshold=args.quality_threshold,
        )
        if args.format == "json":
            output = json.dumps({
                "schema_version": 1,
                "filters": {"task_type": args.task_type, "execution_mode": args.execution_mode},
                "quality_threshold": args.quality_threshold,
                "groups": rows,
            }, indent=2, allow_nan=False)
            print(output)
        else:
            writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    except (sqlite3.Error, ValueError, OSError) as exc:
        print(f"Decision report failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
