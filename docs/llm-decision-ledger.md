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
