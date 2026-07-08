# Client Cloud EU Audit Pack

Scope: use this checklist before installing the self-hosted LiteLLM/Codex routing
stack for a client on Azure or AWS. It is designed for SMB deployments that need
fast due diligence without turning the project into a legal platform.

This is an engineering aid, not legal advice. Keep the completed pack with the
client evidence folder and update it whenever the deployment region, providers,
models, logging, or data categories change.

## 1-Day Audit Flow

### Hour 0-1: Client Intake

Capture these facts before any cloud deployment:

- Client legal entity, EU country, industry, and regulated status.
- Cloud target: Azure, AWS, or both.
- Preferred EU region and backup region.
- Data categories: public, internal, confidential, personal data, special
  category data, secrets, source code, logs, prompts, embeddings.
- User groups: internal staff, contractors, external clients, automated agents.
- Expected traffic: requests per day, TPM/RPM estimate, peak windows.
- Required providers and models, including any local-only or sovereign option.
- Retention needs for prompts, responses, logs, traces, and billing evidence.
- Incident contact, security owner, DPO or privacy owner if applicable.

Minimum decision:

```text
Deploy only after the client confirms data categories, EU region, provider
allow-list, retention period, and incident/security ownership.
```

### Hour 1-3: Regulatory Triage

Classify the deployment with this first-pass matrix:

| Area | Audit question | Evidence to keep |
| --- | --- | --- |
| GDPR/RGPD | Does the system process personal data in prompts, logs, uploads, or outputs? | Data map, retention setting, DPA/SCC status, DPIA decision |
| AI Act | Is the system used for prohibited, high-risk, HR, credit, education, law enforcement, healthcare, or safety decisions? | Use-case classification, human oversight note, model inventory |
| NIS2 | Is the client an essential or important entity, or a supplier to one? | Sector mapping, security controls, incident reporting contact |
| DORA | Is the client a financial entity or ICT third-party provider to finance? | ICT risk controls, exit plan, third-party register |
| ePrivacy | Are communications metadata, cookies, or tracking involved? | Cookie/tracking decision and consent basis |
| Cyber Resilience | Are packaged components delivered as a product or managed service? | SBOM, vulnerability process, update policy |

If any row is uncertain, mark it `needs counsel/client validation` instead of
assuming the lowest-risk answer.

### Hour 3-5: Cloud Architecture Review

Required minimum for both Azure and AWS:

- EU primary region and documented failover choice.
- No secrets in YAML, Dockerfiles, Git, shell history, or logs.
- Secrets stored in Azure Key Vault or AWS Secrets Manager.
- Container image pinned by version or digest.
- Non-root container user, read-only filesystem where feasible, restricted
  capabilities, and no public admin endpoint.
- Ingress behind TLS, authentication, and IP allow-list or private networking.
- Egress restricted to approved model/provider endpoints.
- Prompt and response logging disabled by default.
- Redacted operational logs for route, model alias, latency, status, token
  estimate, cost estimate, and policy decision.
- Backups, retention, and deletion process documented.
- Break-glass key rotation and incident contact documented.

Azure minimum stack:

```text
Azure Container Apps or AKS
Azure Key Vault
Azure Log Analytics / Application Insights
Azure Monitor alerts
Private Link or restricted ingress where possible
Microsoft Defender for Cloud image/security checks
```

AWS minimum stack:

```text
ECS Fargate or EKS
AWS Secrets Manager or Parameter Store with KMS
CloudWatch logs and alarms
ALB with TLS and AWS WAF when public
VPC endpoints or controlled NAT egress where possible
ECR image scan and Security Hub/GuardDuty where available
```

### Hour 5-6: Routing Audit Controls

For the adaptive LiteLLM routing layer, record:

- Active LiteLLM version and deployment config hash.
- Model aliases exposed to users, not raw provider names.
- Provider allow-list and denied providers.
- Region/data-residency policy per provider.
- Whether provider training use is contractually disabled.
- TPM/RPM limits used for pressure scoring.
- Dry-run routing decision for representative prompts.
- Fallback order and conditions.
- 429 avoidance metrics: provider, timestamp, model alias, route selected,
  cooldown state, retry count.
- Cost metrics: estimated cost per route, actual provider billing sample, model
  mix before/after adaptive routing.

Recommended audit log fields:

```json
{
  "timestamp": "2026-07-08T00:00:00Z",
  "tenant": "client-id",
  "request_id": "uuid",
  "route_alias": "codex-default",
  "selected_provider": "provider-alias",
  "selected_region": "eu",
  "dry_run": false,
  "estimated_input_tokens": 1200,
  "estimated_output_tokens": 800,
  "tpm_pressure": 0.42,
  "rpm_pressure": 0.18,
  "cost_score": 0.31,
  "policy_blocks": [],
  "fallback_used": false,
  "http_status": 200
}
```

Do not log raw prompts, raw responses, API keys, bearer tokens, secrets, or
personal data unless the client has explicitly approved that retention.

### Hour 6-7: Evidence Capture

Store these artifacts in the client evidence folder:

- Architecture diagram or text architecture summary.
- Cloud region and network settings screenshot/export.
- Secret manager references, without secret values.
- Container image name, version/digest, and scan result.
- LiteLLM config with secrets redacted.
- Adaptive routing config with dry-run sample output.
- Auth/TLS/firewall settings.
- Logging and retention settings.
- Test results for readiness, one authenticated route, and one dry-run route.
- Incident and key-rotation runbook.

### Hour 7-8: Go/No-Go

Go only if all are true:

- Client approved data categories and intended use.
- EU region and provider allow-list are documented.
- Secrets are in a managed secret store.
- Public exposure, auth, TLS, and network policy are configured.
- Logs are redacted and retention is set.
- Dry-run routing shows policy decisions before live traffic.
- At least one readiness check and one authenticated route test pass.
- Open legal/compliance questions are documented as client-owned risks.

No-go triggers:

- Unknown personal/special-category data handling.
- Public endpoint without authentication.
- Secrets in repository files.
- Raw prompt/response logging enabled by default.
- Provider or region cannot be mapped to the client's residency policy.
- AI Act high-risk use case without human oversight and compliance owner.

## Client Audit Template

```text
Client:
Date:
Auditor:
Cloud target: Azure / AWS / both
EU region:
Backup region:
Deployment mode: private / restricted public / public

Data categories:
Personal data: yes/no/unknown
Special category data: yes/no/unknown
Source code/secrets possible in prompts: yes/no/unknown
Prompt retention:
Response retention:
Operational log retention:

Regulatory triage:
GDPR applies: yes/no/unknown
DPIA needed: yes/no/unknown
AI Act classification:
NIS2 relevance:
DORA relevance:
Client compliance owner:

Security controls:
Secret manager:
TLS:
Authentication:
Ingress restriction:
Egress restriction:
Container scan:
Image pin:
Non-root runtime:

Routing controls:
LiteLLM version:
Provider allow-list:
Denied providers:
EU residency rule:
Dry-run enabled for audit: yes/no
TPM/RPM limits recorded: yes/no
429 tracking enabled: yes/no
Cost tracking enabled: yes/no

Evidence paths:
Config:
Logs:
Screenshots/exports:
Test output:

Go/no-go:
Open risks:
Owner:
Next review date:
```

## Measuring Audit Outcomes

Cost savings:

1. Export provider billing or usage for the baseline period.
2. Export routing logs after adaptive routing is enabled.
3. Compare cost per 1,000 requests, model mix, and premium-provider share.
4. Keep the comparison query or spreadsheet in the evidence folder.

Avoided 429 errors:

1. Count provider `429` responses before adaptive routing.
2. Count provider `429` responses after enabling TPM/RPM pressure scoring.
3. Review cooldown/fallback decisions to confirm traffic moved before repeated
   failures.
4. Track success rate and p95 latency so cost savings do not hide degradation.

Client-ready statement:

```text
The router does not change model compliance by itself. It improves operational
control by making provider choice explicit, auditable, region/policy-aware, and
measurable for cost, latency, and rate-limit risk.
```
