import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "llm_bias_multi_agent.py"
spec = importlib.util.spec_from_file_location("llm_bias_multi_agent", MODULE_PATH)
llm_bias_multi_agent = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = llm_bias_multi_agent
spec.loader.exec_module(llm_bias_multi_agent)


class LLMBiasMultiAgentTests(unittest.TestCase):
    def test_accepts_low_risk_answer(self):
        reducer = llm_bias_multi_agent.BiasReducer()
        result = reducer.evaluate(
            "Summarize a training plan.",
            "The plan should be evaluated with feedback, monitoring, and context-specific review.",
        )

        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["risk_score"], 0.0)
        self.assertTrue(result["revised_answer"].startswith("The plan"))

    def test_rewrites_broad_biased_claims(self):
        reducer = llm_bias_multi_agent.BiasReducer()
        result = reducer.evaluate(
            "Evaluate a credit policy.",
            "All young people are risky, so the loan model should reject them with no bias.",
        )

        self.assertEqual(result["status"], "needs_revision")
        self.assertGreater(result["risk_score"], 0.5)
        revised = result["revised_answer"].casefold()
        self.assertIn("some young people", revised)
        self.assertIn("should route them to documented review", revised)
        self.assertIn("bias-mitigation notes", revised)

    def test_consequential_context_requires_safeguards(self):
        reducer = llm_bias_multi_agent.BiasReducer()
        result = reducer.evaluate(
            "Write a hiring recommendation.",
            "Use a ranking score to select candidates.",
        )
        findings = [
            finding["code"]
            for report in result["agent_reports"]
            for finding in report["findings"]
        ]

        self.assertIn("missing_human_review", findings)
        self.assertIn("missing_auditability", findings)
        self.assertIn("missing_fairness_testing", findings)


if __name__ == "__main__":
    unittest.main()
