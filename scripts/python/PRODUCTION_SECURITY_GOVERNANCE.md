# Production Security & Governance for the Codex LiteLLM Proxy

Scope: this file applies to the local LiteLLM proxy in `C:\Users\user\.codex\litellm-proxy`, exposed only on `127.0.0.1:4000` for Codex and local tests.

For client cloud deployments on Azure or AWS, complete
[`audit/CLIENT_CLOUD_EU_AUDIT.md`](audit/CLIENT_CLOUD_EU_AUDIT.md) before
exposing the proxy outside a local workstation.

## Enforced Locally

- Local Codex route: no LiteLLM bearer token is required while the proxy is bound to `127.0.0.1`; provider API keys still come only from environment variables.
- Secret handling: provider keys stay in user/process environment variables, not in YAML, scripts, logs, or Git.
- Local-only network binding: `start-litellm-proxy.ps1` starts LiteLLM on `127.0.0.1` only.
- Startup safety: `start-litellm-proxy.ps1` checks the launcher, config, Python runtime, and keeps the proxy on localhost.
- Reduced sensitive logging: `disable_spend_logs: true` and `set_verbose: false` are kept enabled.
- Router resilience: retries, timeouts, pre-call checks, cooldowns, fallbacks, context-window fallbacks, and allowed-failure policy are configured in `config.yaml`.
- Health monitoring: background health checks and health-aware routing remain enabled.

## Operator Checklist

1. Run `set-api-keys.ps1` and set whichever upstream provider keys you use, such as `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `HF_TOKEN`.
2. Restart Codex terminals after changing user environment variables.
3. Start with `start-litellm-proxy.ps1`; it should bind to `127.0.0.1:4000` only.
4. Check readiness with `status-litellm-proxy.ps1`.
5. Validate routing with `Test-CodexLiteLLMDispatch.ps1` before relying on the proxy for long jobs.
6. Keep prompts, provider keys, bearer tokens, and PII out of issue reports and logs.
7. If the proxy is ever exposed beyond localhost, re-enable a LiteLLM master key and rotate it after sharing the machine, exporting diagnostics, or changing trust boundaries.

## Governance Rules

- Do not commit real API keys or LiteLLM master keys.
- Do not bind the proxy to `0.0.0.0` unless it is behind explicit authentication, firewall rules, and network policy.
- Do not enable verbose LiteLLM logging for production-like sessions that may include prompts, user data, or secrets.
- Keep high-risk models behind named aliases such as `codex-deep`; callers should not bypass router policy with raw provider names.
- Prefer environment-backed secrets (`os.environ/...`) for every provider credential.
- Review model aliases before adding a new provider so fallback behavior, context-window fallback, and failure thresholds are intentional.

## Budget And Degradation Policy

- 80 percent budget pressure: prefer `codex-light` or cheaper fallback aliases for routine tasks.
- 90 percent budget pressure: reserve `codex-deep` and premium providers for explicitly high-value work.
- Provider instability: rely on health-aware routing, cooldowns, and configured fallbacks before manually retrying the same provider repeatedly.
- Long-context pressure: use the configured context-window fallback chain instead of increasing max tokens blindly.

## If This Moves To Containers Or Kubernetes

Before exposing this outside localhost, add the platform controls from the
production guide and keep client evidence in the audit pack:

- Pin container images by digest and scan them in CI.
- Run as non-root with read-only filesystem, dropped capabilities, and `no-new-privileges`.
- Put secrets in a secret manager or orchestrator secret, never in `config.yaml` or Dockerfiles.
- Add ingress allow-lists, egress controls, and network policies for provider endpoints.
- Enable centralized metrics and audit logging with redaction for secrets, prompts, and PII.
- Define circuit-breaker states and alerts for provider error rates, latency, budget exhaustion, and fallback surges.
- Record EU region, provider allow-list, retention, AI Act/GDPR triage, dry-run
  routing decisions, and 429/cost metrics in
  `audit/CLIENT_CLOUD_EU_AUDIT.md`.

