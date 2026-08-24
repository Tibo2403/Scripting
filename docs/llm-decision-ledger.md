# LLM Decision Ledger

## Positioning

This component is deliberately **not** another model proxy or provider marketplace.
LiteLLM, OpenRouter, direct provider SDKs, and internal gateways remain responsible
for authentication, transport, retries, streaming, and model invocation.

The Decision Ledger adds a provider-neutral intelligence and governance layer:

1. Record the model selected for a task and the alternatives considered.
2. Preserve the reason, estimated cost, and risk level before execution.
3. Attach real latency, cost, success, and reviewed quality after execution.
4. Build evidence by task type instead of relying only on generic benchmarks.
5. Verify that stored routing decisions were not silently modified.

## Why it is different

A router answers: **Which endpoint receives this request now?**

The ledger answers:

- Why was this model appropriate for this precise business task?
- Did the choice deliver the expected quality, cost, and latency?
- Is there enough internal evidence to automate this choice later?
- Can an auditor or customer understand the decision after the fact?

This makes the project complementary to existing gateways and useful for AI
engineering teams operating several providers, local models, or sensitive clients.

## Minimal integration

```python
from llm_decision_ledger import Decision, DecisionLedger, Outcome

ledger = DecisionLedger("data/llm_decisions.sqlite3")
ledger.record_decision(
    Decision(
        request_id="ticket-1842",
        task_type="powershell-security-review",
        selected_model="internal-secure-model",
        alternative_models=("provider-model-a", "provider-model-b"),
        reason="Customer data must remain local; model passed prior security reviews",
        estimated_cost_usd=0.01,
        risk_level="high",
    )
)

# Invoke the model through LiteLLM, OpenRouter, a direct SDK, or another gateway.

ledger.record_outcome(
    Outcome(
        request_id="ticket-1842",
        success=True,
        latency_ms=920,
        actual_cost_usd=0.009,
        quality_score=0.88,
        reviewer="security-reviewer",
    )
)

print(ledger.model_evidence("powershell-security-review"))
```

## SaaS direction

A first sellable product can expose this ledger through an API and dashboard with:

- evidence cards per task, customer, and model;
- explainable routing recommendations before execution;
- shadow comparisons that never send production traffic automatically;
- human review workflows for high-risk outputs;
- exportable governance reports for customers and audits;
- adapters for LiteLLM, OpenRouter, Azure OpenAI, local Ollama, and direct SDKs.

The commercial differentiator is not cheaper API forwarding. It is **decision
intelligence for reliable multi-model AI engineering**.

## Product boundary: Decision Control Plane vs LiteLLM

The project treats LiteLLM as the execution gateway, not as a competitor to
rebuild. LiteLLM owns provider authentication, OpenAI-compatible transport,
streaming, retries, fallbacks, load balancing, and technical budget enforcement.

The Decision Control Plane owns the business decision before and after that
execution:

```text
Application or agent
        |
        v
Decision Control Plane
task classification, data boundary, risk, approval, explanation, evidence
        |
        v
LiteLLM or another gateway
authentication, provider invocation, retry, fallback, streaming, metering
        |
        v
Model providers and local models
        |
        v
Outcome, reviewed quality, and cost returned to the Decision Ledger
```

Routing by cost, latency, or provider health alone is not the product moat.
The moat is the evidence accumulated for a precise task and customer policy,
plus the ability to prove which policy authorized a live execution.

## Mandatory guardrails

The ledger applies these rules before recording a decision intended for live
execution:

1. High- and critical-risk decisions require a named human approver.
2. Restricted data must remain inside the local execution boundary.
3. A configured maximum estimated cost is a hard ceiling, not a soft score.
4. Risk, data classification, boundary, execution mode, and policy version use
   explicit validated values.
5. A rejected live decision fails closed and is never silently downgraded.
6. Shadow decisions may be recorded for evaluation because they dispatch no
   production traffic.
7. Governance metadata is included in the integrity hash.

These are minimum controls. Provider allowlists, regional residency checks,
separation of approver and operator, cryptographic signatures, retention rules,
and append-only remote storage remain required before production deployment.

## Explicit separation from tokenized finance

The Decision Control Plane is an AI infrastructure and governance project. It
does not issue tokens, hold collateral, manage liquidity, price bonds, or make
financial promises. The tokenized-finance project is a separate product and
risk domain with its own repository boundary, governance, legal review, and
financial safeguards.

The only permitted integration is conventional: a finance application may call
the Decision Control Plane to govern its AI model usage. That integration does
not transfer financial responsibilities into the router and does not make the
ledger a financial settlement system.

## Delivery sequence

1. Stabilize the policy schema and SQLite ledger with fail-closed tests.
2. Add a LiteLLM callback adapter without duplicating proxy behavior.
3. Add shadow comparisons and reviewed quality evidence by task type.
4. Add a policy API and human-approval workflow.
5. Move integrity records to signed, append-only storage before multi-tenant use.
