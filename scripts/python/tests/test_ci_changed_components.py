import unittest

from scripts.python.ci_changed_components import classify_paths


class ClassifyPathsTests(unittest.TestCase):
    def test_documentation_does_not_select_a_component(self) -> None:
        self.assertFalse(any(classify_paths(["README.md"]).values()))

    def test_language_checks_only_select_matching_scripts(self) -> None:
        result = classify_paths(
            ["scripts/tool.ps1", "scripts/tool.sh", "scripts/python/tool.py"]
        )
        self.assertTrue(result["powershell"])
        self.assertTrue(result["bash"])
        self.assertTrue(result["python"])

    def test_non_python_files_in_python_directory_skip_python(self) -> None:
        powershell = classify_paths(["scripts/python/helper.ps1"])
        documentation = classify_paths(["scripts/python/README.md"])
        self.assertTrue(powershell["powershell"])
        self.assertFalse(powershell["python"])
        self.assertFalse(documentation["python"])

    def test_python_runtime_configuration_selects_python(self) -> None:
        result = classify_paths(["scripts/python/codex-routing-policy.yaml"])
        self.assertTrue(result["python"])

    def test_dedicated_crewai_files_skip_generic_language_checks(self) -> None:
        result = classify_paths(["scripts/python/openclaw_crewai_admin/setup.sh"])
        self.assertFalse(result["bash"])
        self.assertFalse(result["python"])

    def test_shared_powershell_validator_also_selects_pra(self) -> None:
        result = classify_paths(["scripts/powershell/Test-ScriptSyntax.ps1"])
        self.assertTrue(result["powershell"])
        self.assertTrue(result["pra"])

    def test_dedicated_crewai_project_skips_generic_python(self) -> None:
        result = classify_paths(["scripts/python/openclaw_crewai_admin/app.py"])
        self.assertFalse(result["python"])

    def test_experimental_projects_are_independent(self) -> None:
        tokenized = classify_paths(["tokenized_llm_finance/python/model.py"])
        shell = classify_paths(["openclaw-akash-dual-agents/install.sh"])
        pra = classify_paths(["pra/Invoke-Pra.ps1"])
        self.assertTrue(tokenized["tokenized"])
        self.assertFalse(tokenized["shell_prototypes"])
        self.assertTrue(shell["shell_prototypes"])
        self.assertFalse(shell["pra"])
        self.assertTrue(pra["pra"])
        self.assertFalse(pra["tokenized"])

    def test_experimental_documentation_skips_expensive_jobs(self) -> None:
        result = classify_paths(
            [
                "tokenized_llm_finance/README.md",
                "openclaw-akash-dual-agents/README.md",
                "pra/PRA_V2_Operationnel.md",
            ]
        )
        self.assertFalse(result["tokenized"])
        self.assertFalse(result["shell_prototypes"])
        self.assertFalse(result["pra"])

    def test_each_workflow_change_selects_its_jobs(self) -> None:
        main = classify_paths([".github/workflows/script-validation.yml"])
        experimental = classify_paths(
            [".github/workflows/experimental-validation.yml"]
        )
        self.assertTrue(all(main[name] for name in ("maturity", "powershell", "bash", "python")))
        self.assertTrue(
            all(experimental[name] for name in ("tokenized", "shell_prototypes", "pra"))
        )

    def test_catalog_or_root_directory_change_selects_maturity(self) -> None:
        catalog = classify_paths(["project-maturity.toml"])
        root = classify_paths([], top_level_directories_changed=True)
        self.assertTrue(catalog["maturity"])
        self.assertTrue(root["maturity"])


if __name__ == "__main__":
    unittest.main()
