# SMB LLM Pilot Pack

This folder contains day-one documentation templates for a small or medium
business that wants to run a controlled self-hosted LLM pilot with LiteLLM,
optional Ollama, and optional Azure or AWS hosting.

Use these files as a private working pack. Copy them into the customer or
company workspace before adding names, billing details, internal hostnames,
tenant IDs, diagrams, or security decisions.

## Setup Flow

1. Fill `LLM_ALLOWED_USE.md` before any live prompt testing.
2. Fill `LLM_KEYS.md` with secret locations and owners, not raw secret values.
3. Run the one-day implementation from `../smb-llm-self-hosting-one-day.md`.
4. Record start, stop, healthcheck, and rollback commands in `LLM_OPERATIONS.md`.
5. Capture baseline and pilot measurements in `LLM_METRICS.md`.
6. Close the day with `LLM_PILOT_RESULTS.md`.

## Files

| File | Purpose |
| --- | --- |
| `LLM_ALLOWED_USE.md` | Defines allowed, review-first, and blocked use cases. |
| `LLM_KEYS.md` | Tracks where keys are stored, who owns them, and rotation dates. |
| `LLM_OPERATIONS.md` | Provides start, stop, status, healthcheck, rollback, and incident commands. |
| `LLM_METRICS.md` | Captures latency, cost, fallback, and avoided `429` measurements. |
| `LLM_PILOT_RESULTS.md` | Summarizes workflows tested, issues, decisions, and next actions. |

## Day-One Acceptance Criteria

- A named owner approves allowed, review-first, and blocked prompt classes.
- Provider keys are stored outside the repository.
- LiteLLM starts and stops with documented commands.
- At least one local or private route works.
- Any cloud fallback route is explicitly approved.
- A dry-run adaptive route decision can be captured when the risk router is used.
- Cost, latency, fallback count, and `429` count are recorded.
- Rollback returns users to the standard profile.

## Local, Azure, or AWS Notes

For a local workstation pilot, keep the proxy bound to `127.0.0.1` unless a
reviewed reverse proxy is in place.

For Azure or AWS, keep the gateway private by default:

- restrict access with VPN, private subnet, bastion, or zero-trust access;
- store secrets in Azure Key Vault or AWS Secrets Manager;
- tag resources with owner, pilot end date, cost center, and data class;
- configure daily budget alerts before enabling GPU routes;
- send operational logs to Azure Monitor, CloudWatch, or a private SIEM.

Cloud hosting keeps the gateway self-managed, but prompts sent to external model
providers still follow the provider approval and data-handling policy.
