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
    def test_manager_returns_standard_prompt_report(self):
        manager = llm_bias_multi_agent.MultiAgentPromptManager(max_rounds=2)
        result = manager.evaluate(
            "Summarize a general product launch plan.",
            "Everyone will certainly love this launch.",
        )

        self.assertEqual(result["manager"], "multi_agent_prompt_manager")
        self.assertEqual(result["status"], "accepted")
        self.assertGreaterEqual(result["round_count"], 1)
        self.assertEqual(result["rounds"][0]["status"], "needs_revision")
        self.assertIn("rounds", result)
        self.assertIn("revised_answer", result)
        self.assertNotIn("certainly", result["revised_answer"].casefold())
        self.assertNotIn("will may", result["revised_answer"].casefold())
        self.assertEqual(result["revised_answer"].count("Bias-mitigation notes:"), 1)

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

    def test_custom_agent_can_be_plugged_into_manager(self):
        class LengthAgent(llm_bias_multi_agent.ReviewAgent):
            name = "length_agent"

            def review(self, prompt, answer):
                if len(answer) <= 20:
                    return llm_bias_multi_agent.AgentReport(self.name, ())
                return llm_bias_multi_agent.AgentReport(
                    self.name,
                    (
                        llm_bias_multi_agent.Finding(
                            self.name,
                            "too_long",
                            0.5,
                            "answer length",
                            "Shorten the answer.",
                        ),
                    ),
                )

        manager = llm_bias_multi_agent.MultiAgentPromptManager(agents=(LengthAgent(),))
        result = manager.evaluate("Reply briefly.", "This response is intentionally longer than requested.")
        findings = result["agent_reports"][0]["findings"]

        self.assertEqual(result["status"], "needs_revision")
        self.assertEqual(findings[0]["code"], "too_long")



    def test_revise_replaces_existing_notes_with_windows_line_endings(self):
        manager = llm_bias_multi_agent.MultiAgentPromptManager()
        answer = (
            "All young people are risky.\r\n\r\n"
            "Bias-mitigation notes:\r\n"
            "- Old note.\r\n"
        )
        findings = (
            llm_bias_multi_agent.Finding(
                "stereotype_agent",
                "group_generalization",
                0.82,
                "All young people",
                "Replace broad group claims with scoped, evidence-based language.",
            ),
        )

        revised = manager.revise(answer, findings)

        self.assertEqual(revised.count("Bias-mitigation notes:"), 1)
        self.assertNotIn("Old note.", revised)
        self.assertTrue(revised.startswith("some young people are risky."))

if __name__ == "__main__":
    unittest.main()
