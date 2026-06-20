# LLM Bias Multi-Agent Reducer

Standalone deterministic multi-agent review layer for reducing bias in generic LLM outputs.

It does not call an LLM provider. It can sit after any model output and performs:

- protected-attribute review;
- stereotype and broad-generalization review;
- overconfidence and weak-evidence review;
- inclusion and alternatives review;
- safeguards review for consequential domains such as finance, hiring, housing, medicine, education, or insurance.

## Usage

```bash
python scripts/python/llm_bias_multi_agent.py answer.txt --prompt-file prompt.txt --pretty
```

or:

```bash
echo "All young users are risky, so the loan model should reject them." | \
  python scripts/python/llm_bias_multi_agent.py --prompt "Evaluate a credit policy" --pretty
```

The output is JSON:

```json
{
  "risk_score": 0.93,
  "status": "needs_revision",
  "finding_count": 6,
  "agent_reports": [],
  "revised_answer": "..."
}
```

## How To Use With Any LLM

1. Send a prompt to your LLM.
2. Pass the LLM answer to `llm_bias_multi_agent.py`.
3. If `status` is `needs_revision`, use `revised_answer` or feed the findings back into your LLM for another revision round.
4. For consequential decisions, keep human review, audit logs, subgroup metrics, and domain-specific validation.

This is a first-pass guardrail. It reduces obvious biased wording and flags missing safeguards, but it does not replace statistical fairness testing on real data.
