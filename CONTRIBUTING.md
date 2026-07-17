# Contributing

Thank you for improving the Scripting Toolkit.

## Before opening a pull request

1. Create a focused branch from `main`.
2. Keep the change limited to one clear purpose.
3. Never include credentials, real customer data, tenant identifiers, scan output, packet captures, or unauthorized targets.
4. Add or update documentation when behavior changes.
5. Add a regression test for bug fixes when practical.

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

Explain what changed, why it is needed, how it was validated, and any security or compatibility impact. Privileged, network, or offensive-security behavior must include safe defaults and a dry-run path where possible.