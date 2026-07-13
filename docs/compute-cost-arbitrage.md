# Compute and LLM API Cost Arbitrage

`scripts/python/compute_cost_arbitrage.py` compares three ways to serve an LLM
workload without changing live routing:

- hardware you own, including electricity, idle consumption, PUE, and monthly
  hardware amortization;
- rented GPU compute, including an accepted Akash provider bid or another
  cloud hourly price;
- a hosted LLM API, with separate input and output token prices.

The tool rejects choices below a minimum quality score or without enough
monthly inference capacity, then recommends the cheapest remaining candidate.
It is dependency-free and produces either a readable Markdown report or JSON
for another automation.

## Public Price Catalogs

Generate a fresh API catalog from LiteLLM's public model cost map:

```powershell
python scripts\python\build_public_llm_price_catalog.py `
  --base-catalog scripts\python\public-compute-price-snapshot.json `
  --output public-llm-cost-catalog.json
```

At the 2026-07-13 verification, the normalizer found 2,214 token-priced chat
models across 86 LiteLLM providers and merged 13 directly usable compute
offers. This is broad discovery data, not an
invoice-grade authority: verify the shortlisted model on the provider's
official pricing page before changing production routing.

The repository also contains a dated compute snapshot at
`scripts/python/public-compute-price-snapshot.json`. Its directly usable
entries cover published Runpod GPU pods and an AWS Capacity Block instance.
Google Cloud GPU-component prices and Akash planning ranges are kept under
`reference_only`, so they cannot accidentally win an all-in comparison. Add
Google's VM, disk, and network cost; for Akash, use the bid actually accepted
by the deployment.

Use `catalog_options` to add selected public prices to a scenario while keeping
quality, throughput, billed hours, and fixed costs local to the workload:

```powershell
python scripts\python\compute_cost_arbitrage.py `
  --config scripts\python\compute-cost-arbitrage.catalog.example.json `
  --catalog public-llm-cost-catalog.json
```

To compare compute only, the static compute snapshot can also be passed
directly as `--catalog`. A scenario can mix manual, API, and compute catalog
options when the generated merged catalog is used. Currency conversion is never inferred: when
the catalog is in USD and the report is in EUR, set
`currency_conversion.USD` to the dated rate used for the analysis.

Each normalized entry retains its provider, fetch timestamp, LiteLLM model id,
and source URL. Refresh the generated API file on a schedule and preserve old
snapshots if decisions must be auditable.

## Daily and Weekly CSV Trends

The arbitrage command can append every candidate from the current run to a
raw history CSV and regenerate a daily and weekly recap in the same run:

```powershell
python scripts\python\compute_cost_arbitrage.py `
  --config scripts\python\compute-cost-arbitrage.catalog.example.json `
  --catalog public-llm-cost-catalog.json `
  --history-csv reports\llm-cost-history.csv `
  --trend-csv reports\llm-cost-trends.csv `
  --trend-period both `
  --output reports\latest-arbitrage.md
```

`llm-cost-history.csv` is append-only and stores one observation per candidate,
including the UTC timestamp, eligibility, selected route, estimated monthly
cost, cost per million tokens, hourly compute price, electricity price, and
energy consumption when applicable. Keep this file between runs: it is the
source for the trend calculations.

`llm-cost-trends.csv` is rewritten as a recap suitable for Excel, LibreOffice,
Power BI, or another reporting tool. For each candidate and currency it
contains:

- daily and ISO-week periods, with weeks running Monday through Sunday;
- observation count and quality-eligible rate;
- average, minimum, and maximum monthly cost;
- absolute and percentage change from the previous available period;
- average cost per million tokens, hourly compute price, kWh tariff, and kWh;
- number of times the candidate was selected as the primary route.

Use `--trend-period daily` or `--trend-period weekly` when only one aggregation
is needed. `--observed-at 2026-07-13T08:00:00Z` provides a reproducible timestamp
for an imported or backfilled observation; normal scheduled runs should omit it
so the current UTC time is used. Different currencies are never merged.

For a daily Windows Task Scheduler job, run the catalog refresh first, then the
arbitrage command above. On Linux or a cloud VM, the same two commands can be
placed in cron, for example at 06:00 UTC:

```cron
0 6 * * * cd /opt/scripting && python3 scripts/python/build_public_llm_price_catalog.py --base-catalog scripts/python/public-compute-price-snapshot.json --output reports/public-llm-cost-catalog.json && python3 scripts/python/compute_cost_arbitrage.py --config scripts/python/compute-cost-arbitrage.catalog.example.json --catalog reports/public-llm-cost-catalog.json --history-csv reports/llm-cost-history.csv --trend-csv reports/llm-cost-trends.csv --trend-period both --output reports/latest-arbitrage.md
```

Run only one writer per history file. If several agents or regions collect
prices concurrently, give each collector its own history CSV and merge them in
a controlled reporting job to avoid interleaved writes.

## Quick Start

Copy the example before replacing its illustrative prices and benchmarks:

```powershell
Copy-Item scripts\python\compute-cost-arbitrage.example.json `
  compute-cost-arbitrage.local.json
python scripts\python\compute_cost_arbitrage.py `
  --config compute-cost-arbitrage.local.json
```

JSON output is convenient for a scheduler or an OpenClaw tool:

```powershell
python scripts\python\compute_cost_arbitrage.py `
  --config compute-cost-arbitrage.local.json --format json
```

Run a sensitivity test without editing the file:

```powershell
python scripts\python\compute_cost_arbitrage.py `
  --config compute-cost-arbitrage.local.json `
  --min-quality 82 --electricity-price 0.12
```

The override creates a tariff named `CLI override`. This makes it easy to test
an off-peak contract, a renewable-energy surplus, or a target electricity
price.

## Inputs to Measure

Do not treat the example configuration as a current quotation. Update
`pricing_date` and collect:

- monthly input and output tokens from the real workload;
- measured generation throughput for the exact model, quantization, GPU, and
  context profile;
- wall-socket load and idle wattage, not GPU TDP alone;
- the all-in electricity price and PUE; use `1` only when cooling and facility
  overhead are genuinely included elsewhere;
- hardware purchase cost, residual value, amortization period, and recurring
  fixed costs;
- the accepted cloud or Akash hourly bid, including any persistent services
  that remain online;
- current API input and output prices;
- quality scores from the same representative evaluation set for every model.

Quality uses a user-defined 0-to-100 scale. For example, score tool-call
success, answer correctness, latency constraints, language quality, and safety
on a frozen workload sample. The number is comparable only when every option
uses the same rubric. Set `minimum_quality` to the lowest acceptable score; the
reported `quality_margin` shows how much headroom remains.

## Cost Model

For owned hardware, the monthly estimate is:

```text
required hours = total tokens / measured tokens per second / 3600
energy kWh = ((load W * inference hours) + (idle W * idle hours)) / 1000 * PUE
monthly cost = energy kWh * tariff + amortization + fixed cost
```

Amortization is `(purchase cost - residual value) / amortization months`.
The report also calculates the maximum electricity price at which owned
hardware still beats the cheapest quality-eligible API. This break-even figure
is unavailable when no eligible API baseline exists.

For rented compute, cost is the declared online lease hours multiplied by the
hourly bid plus fixed cost. For an API, cost is input and output token usage
multiplied by their respective per-million-token prices.

The model deliberately stays conservative and transparent. It does not yet
price network egress, taxes, operator labor, failure redundancy, cold starts,
or queueing. Add these to `fixed_monthly_cost` when they are material.

## Arbitration with LiteLLM and OpenClaw

This utility is a decision layer, not a second proxy:

```text
measurements and current prices
        -> compute_cost_arbitrage.py
        -> approved LiteLLM model alias
        -> OpenClaw agent calls LiteLLM
        -> local Ollama, Akash GPU, other cloud, or hosted API
```

The JSON recommendation contains `litellm_model`. An operator or scheduled
automation can map the selected alias to the relevant LiteLLM deployment. Keep
the change approval-based at first: validate the report, update the agent's
allowed alias or LiteLLM policy, run a smoke test, then observe quality and
cost. The calculator never edits LiteLLM or OpenClaw configuration itself.

For strict sovereignty, include only self-hosted candidates and keep OpenClaw
fallbacks empty. For cost-first agents, declare both sovereign and API aliases,
but keep a quality floor and an explicit provider allowlist. Different agents
can use different workload files and quality thresholds.

## Reducing Electricity Cost Safely

- benchmark batch inference and run deferrable jobs during verified off-peak
  or renewable-surplus windows;
- shut down rented deployments when no service-level objective requires them;
- reduce idle hours, while accounting for model load and cold-start time;
- compare quantizations on quality per kWh, not throughput alone;
- rerun the report when electricity, provider bids, API prices, model versions,
  or workload volumes change.

Akash pricing is dynamic and provider bids depend on requested resources, so
enter the bid you can actually lease rather than a static example value. A
monthly report is useful for planning; a shorter refresh interval is preferable
when spot-like prices or workloads move quickly.

## Safety Boundary

The report is an estimate, not an SLA or billing statement. Do not automate a
production route switch solely from price. Require capacity, quality, health,
data-residency, privacy, and fallback checks as separate gates.
