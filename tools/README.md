# Experimental code analysis tools

These scripts are prototypes, classified in `project-maturity.toml`. Run commands
from the repository root on Linux or Git Bash, with Python 3 and the dependencies
for the selected script installed in an isolated environment. No administrator
privileges are required.

| Entry point | Dependencies and configuration | Effects |
|---|---|---|
| `bash tools/analyze-ai.sh` | `requests`, `INKLING_API_KEY`, `INKLING_API_URL` | Sends source files to the configured provider and overwrites `AI_REPORT.md` |
| `bash tools/refactor.sh` | Ruff and pytest on PATH | Runs Ruff fixes and formatting on the current directory, then tests and displays the diff |

The analysis scans Python, JavaScript, TypeScript and shell files beneath the
current directory, excluding `.git`, `node_modules`, `.venv` and `venv`. Only run
it on code authorized for transmission to the configured service. Provider calls
may incur charges. Store credentials outside Git. Generated `AI_REPORT.md` is
ignored by Git.

The refactoring prototype currently tolerates pytest failures, so its exit code
does not establish that tests passed; inspect the test results separately.

Reproducible offline checks (also run by the maturity-catalog CI job):

```bash
python scripts/python/check_project_maturity.py
python -m compileall -q tools
bash -n tools/analyze-ai.sh tools/refactor.sh
```

These checks validate classification and syntax only. No live provider calls or
automatic refactoring are run in CI.
