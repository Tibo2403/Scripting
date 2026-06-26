# Finance Bias Evaluator

Small rule-based evaluator for finance-oriented security and algorithmic-bias review prompts.

The script reads a technical proposal from stdin or from a UTF-8 file and prints exactly one JSON object:

```json
{
  "statut": 0,
  "confiance": 0.99,
  "justification_technique": "..."
}
```

## Why this exists

The evaluator is intentionally conservative for finance use cases. A proposal fails when it contains a risky pattern or when it omits core controls such as fairness metrics, human review, audit logging, data governance, or security controls.

It can detect examples such as:

- protected attributes or possible proxies, for example age, gender, postal code, or zip code;
- fully automated financial decisions without human review;
- opaque or unauditable systems;
- exposed secrets or tokens;
- unrealistic claims such as guaranteed fairness or 100% absence of bias;
- hallucinated helper functions such as `detect_all_bias` or `guarantee_fairness`.

## Usage

```bash
python scripts/python/finance_bias_evaluator.py proposal.txt
```

or:

```bash
echo "We use fairness metrics, human review, audit logs, data governance and encryption." | \
  python scripts/python/finance_bias_evaluator.py
```

Pretty output:

```bash
python scripts/python/finance_bias_evaluator.py proposal.txt --pretty
```

## Validation examples

Valid-looking proposal:

```bash
echo "We use fairness metrics, human review, audit logs, data governance and encryption to assess credit risk." | \
  python scripts/python/finance_bias_evaluator.py
```

Risky proposal:

```bash
echo "The model auto-approves loans using age and zip code with no human review." | \
  python scripts/python/finance_bias_evaluator.py
```

## Limitations

This is a deterministic static checker, not a formal proof of fairness or security. It should be used as a first-pass guardrail before deeper review, statistical fairness testing, model validation, and legal/compliance assessment.
