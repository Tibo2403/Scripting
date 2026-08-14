# Contributing

Thank you for improving the Scripting Toolkit.

## Before opening a pull request

1. Create a focused branch from `main`.
2. Keep the change limited to one clear purpose.
3. Never include credentials, real customer data, tenant identifiers, scan output, packet captures, or unauthorized targets.
4. Add or update documentation when behavior changes.
5. Add a regression test for bug fixes when practical.
6. Identify the affected project and its maturity in `project-maturity.toml`.

## Project maturity

This repository uses two explicit levels: **usable** and **experimental**. Read
[`docs/project-maturity.md`](docs/project-maturity.md) before expanding a project scope or changing
its level. New top-level project directories must be registered in `project-maturity.toml`; creating
a separate GitHub repository is not required.

Run the catalog check for every structural change:

```bash
python scripts/python/check_project_maturity.py
```

Do not describe an experimental project as production-ready. Promotion to usable must include the
documentation, safe defaults, CI coverage and risk evidence listed in the maturity policy.

## Validation

Run the checks relevant to your change:

```bash
find scripts -name "*.sh" -print0 | xargs -0 -n1 bash -n
find scripts -name "*.sh" -print0 | xargs -0 shellcheck --severity=error
python -m unittest discover -s scripts/python/tests -v
bash scripts/tests/test-linux-safety.sh
```

For PowerShell changes:

```powershell
./scripts/powershell/Test-ScriptSyntax.ps1 -Path ./scripts
Invoke-ScriptAnalyzer -Path ./scripts -Recurse -Settings ./PSScriptAnalyzerSettings.psd1
```

## Pull requests

Use the repository pull request template. State the affected maturity level and whether the change
preserves, promotes or demotes it. Privileged, network, or offensive-security behavior must include
safe defaults and a dry-run path where possible.
