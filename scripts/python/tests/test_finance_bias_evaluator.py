import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "finance_bias_evaluator.py"
spec = importlib.util.spec_from_file_location("finance_bias_evaluator", MODULE_PATH)
finance_bias_evaluator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = finance_bias_evaluator
spec.loader.exec_module(finance_bias_evaluator)


class FinanceBiasEvaluatorTests(unittest.TestCase):
    def test_flags_missing_controls_and_protected_attributes(self):
        result = finance_bias_evaluator.evaluate(
            "The model auto-approves loans using age and zip code with no audit trail."
        )

        self.assertEqual(result["statut"], 0)
        self.assertGreaterEqual(result["confiance"], 0.8)
        self.assertIn("detected", result["justification_technique"])

    def test_accepts_controlled_proposal(self):
        result = finance_bias_evaluator.evaluate(
            "The credit workflow uses fairness metrics, human review, audit logs, "
            "data governance, privacy controls, encryption, and least privilege."
        )

        self.assertEqual(result["statut"], 1)
        self.assertGreater(result["confiance"], 0.7)


if __name__ == "__main__":
    unittest.main()
