# LLM Metrics

Use this file to prove whether the pilot improves cost, latency, and reliability.

## Baseline

Capture this before users start the pilot.

| Metric | Value | Command or source | Notes |
| --- | --- | --- | --- |
| LiteLLM health | TBD | `healthcheck-litellm-routes.ps1` | TBD |
| Local model latency | TBD | `Measure-QwenLocalSpeed.ps1` | TBD |
| Proxy dispatch latency | TBD | `measure-litellm-dispatch.ps1` | TBD |
| Adaptive router latency | TBD | `measure-risk-adjusted-dispatch.ps1` | Optional |
| Provider 429 count | TBD | Provider logs or router metrics | TBD |
| Estimated cost per 100 requests | TBD | Token estimate | TBD |

## Pilot Log

| Date/time | Workflow | Alias | Route | Requests | Input tokens | Output tokens | Avg latency | 429 count | Fallback count | Estimated cost | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## Cost Formula

Use provider pricing from the approved billing source.

```text
estimated_cost =
  (input_tokens / 1_000_000 * input_price_per_1m_tokens)
  + (output_tokens / 1_000_000 * output_price_per_1m_tokens)
```

For a route comparison:

```text
savings =
  baseline_cloud_cost
  - pilot_actual_cost
```

## Avoided 429 Definition

Count an avoided `429` when the router would have selected an overloaded route
but dry-run, fallback, or risk scoring moved the request to a healthy route.

Record:

- timestamp;
- original alias;
- avoided provider;
- selected provider;
- token estimate;
- router reason;
- whether the user accepted the response.

## Success Thresholds

| Goal | Target | Result |
| --- | --- | --- |
| Cost | At least 15% lower cost for approved low-risk workflows | TBD |
| Reliability | Fewer provider `429` errors than baseline | TBD |
| Latency | p95 latency acceptable for pilot workflows | TBD |
| Safety | No secrets or blocked data in prompts | TBD |
| Operations | Rollback tested successfully | TBD |
