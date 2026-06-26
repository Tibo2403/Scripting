# LLM Multi-Agent Prompt Manager

Standalone deterministic multi-agent manager for reviewing and improving generic LLM prompt returns.

It does not call an LLM provider. It sits after any model output and performs a standard orchestration loop:

1. receive the original prompt and LLM answer;
2. run a panel of review agents;
3. aggregate findings and a risk score;
4. revise the answer conservatively;
5. optionally repeat the review for several rounds.

The default panel focuses on bias and safeguard review:

- protected-attribute review;
- stereotype and broad-generalization review;
- overconfidence and weak-evidence review;
- inclusion and alternatives review;
- safeguards review for consequential domains such as finance, hiring, housing, medicine, education, or insurance.

## Usage

```bash
python scripts/python/llm_bias_multi_agent.py answer.txt --prompt-file prompt.txt --max-rounds 2 --pretty
```

or:

```bash
echo "All young users are risky, so the loan model should reject them." | \
  python scripts/python/llm_bias_multi_agent.py --prompt "Evaluate a credit policy" --pretty
```

The output is JSON:

```json
{
  "manager": "multi_agent_prompt_manager",
  "round_count": 1,
  "risk_score": 0.93,
  "status": "needs_revision",
  "finding_count": 6,
  "agent_reports": [],
  "revised_answer": "..."
}
```

## How To Use With Any LLM

1. Send a prompt to your LLM.
2. Pass the LLM answer to `llm_bias_multi_agent.py` or to `MultiAgentPromptManager` in Python.
3. If `status` is `needs_revision`, use `revised_answer` or feed the findings back into your LLM for another revision round.
4. For consequential decisions, keep human review, audit logs, subgroup metrics, and domain-specific validation.

## Python API

```python
from llm_bias_multi_agent import MultiAgentPromptManager

manager = MultiAgentPromptManager(max_rounds=2)
report = manager.evaluate(
    prompt="Write a recommendation.",
    answer="Everyone will certainly benefit from this policy.",
)
print(report["revised_answer"])
```

You can plug in custom agents by implementing `ReviewAgent.review(prompt, answer)` and returning an `AgentReport`.

This is a first-pass manager. It reduces obvious biased wording and flags missing safeguards, but it does not replace task-specific evaluation, statistical fairness testing, security review, or human judgment.
