# OpenClaw Temporary Orchestrator

OpenClaw is used only as a temporary orchestration layer for the "1 Day Implementation" installation workflow.

It is not a runtime dependency, not a required deployment component, and not a permanent architecture layer for this project. After the installation day, the project must remain usable with its normal scripts, documentation, tests, and GitHub workflow without OpenClaw.

## Temporary Role

During the implementation day, OpenClaw may coordinate the workflow by:

- splitting the installation work into small, testable tasks;
- calling Codex for concrete implementation steps;
- sequencing repository audit, install, validation, and reporting scripts;
- checking test results before moving to the next task;
- preparing the final installation report.

## Fast Deployment Without Codex

If Codex is unavailable or should not be used for a customer deployment, run the
workflow in operator-only mode:

1. Use OpenClaw only as a checklist coordinator.
2. Run the repository scripts manually.
3. Record command outputs in `1-day-implementation/reports/installation-report.md`.
4. Do not ask Codex to edit files or perform implementation.
5. Keep all changes explicit, reviewed, and reversible.

The fast path is:

```powershell
.\1-day-implementation\scripts\audit_repo.ps1
.\1-day-implementation\scripts\install.ps1 -NoCodex
.\1-day-implementation\scripts\run_tests.ps1
.\1-day-implementation\scripts\validate_installation.ps1
```

## Boundaries

OpenClaw must not:

- introduce heavy dependencies;
- require a permanent service, agent, or daemon;
- replace the repository scripts as the source of truth;
- bypass authorization, security checks, or test gates;
- create vendor lock-in for future deployments.

## Expected Flow

1. Audit the repository and installation target.
2. Split the work into small tasks.
3. Ask Codex to implement one task at a time.
4. Run validation scripts after meaningful changes.
5. Record test results and risks in the final report.
6. Confirm that the project still works without OpenClaw.

## Exit Criteria

OpenClaw can be removed from the workflow when:

- installation scripts are documented;
- validation scripts run cleanly;
- the final report is complete;
- the client or operator can repeat the installation using repository files only.
