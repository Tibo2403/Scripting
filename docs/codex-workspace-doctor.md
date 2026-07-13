# Codex Workspace Doctor

`Optimize-CodexWorkspace.ps1` prepares a repository before a Codex CLI session.
It works locally without an API key, proxy, or external PowerShell module.

## Analyze a Project

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath C:\Users\user\Documents\HealthApp
```

The report includes:

- detected languages and frameworks;
- recommended validation commands;
- large files that deserve review before adding them to context;
- generated directories skipped during the scan, including nested paths;
- directory links skipped to avoid duplicate traversal or recursive loops;
- possible secrets, with values intentionally hidden;
- large text files skipped by the configurable secret scan size limit;
- the status of `AGENTS.md`;
- Git branch and uncommitted changes;
- missing context files such as `README.md` or `.gitignore`;
- a readiness score and prioritized recommendations.

## Measure Efficiency

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -Validate `
  -ReportPath .\codex-workspace-report.json
```

Without `-Validate`, efficiency is reported as `not-measured`. With
`-Validate`, the doctor runs static checks and calculates:

```text
Efficiency = 50% workspace readiness + 50% successful executable validations
```

The JSON report includes each validation status and duration. Failed or
timed-out native commands also include a limited, redacted output tail. This
measures workspace preparation and automated verification, not model quality or
token usage.

Tests and builds defined by a project can execute arbitrary repository code.
Run them only for a repository that you trust:

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -Validate `
  -AllowProjectCommands
```

Native validation commands stop after five minutes by default. Adjust the
timeout and retained diagnostic size when needed:

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -Validate `
  -AllowProjectCommands `
  -ValidationTimeoutSeconds 120 `
  -ValidationLogLineLimit 30
```

For Python validations, the doctor prefers a project-local
`.venv\Scripts\python(.exe|.cmd)` when present, then falls back to `python`,
`python3`, or `py -3`.

## Enforce a CI Policy

`-FailOn` returns a non-zero exit code when one of the selected conditions is
found. The JSON report is still written before the script exits.

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -Validate `
  -FailOn Secret,ValidationFailure,LowReadiness `
  -MinimumReadinessScore 80 `
  -ReportPath .\codex-workspace-report.json
```

Use `-AllowProjectCommands` as well when CI should run repository-defined tests
and builds. `-FailOn ValidationFailure` requires `-Validate`.

## Generate Codex Guidance

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath C:\Users\user\Documents\HealthApp `
  -Fix
```

`-Fix` creates or updates a marked section in `AGENTS.md`. Existing human
instructions outside that section are preserved.

## Disable Generated Guidance

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -Disable
```

`-Disable` removes only the managed section. Existing human instructions are
preserved. If `AGENTS.md` contains only generated guidance, the file is removed.

## Save a JSON Report

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -ReportPath .\codex-workspace-report.json
```

The JSON report never contains detected secret values.

Text files larger than `1 MB` are reported but not scanned for secrets by
default. A scan with skipped text files reports `partial` instead of `passed`
when no secret finding requires review. Adjust the limit for trusted
repositories when needed:

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -SecretScanMaxFileSizeMB 5
```

Replacing an existing report requires explicit confirmation:

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -ReportPath .\codex-workspace-report.json `
  -ForceReportOverwrite
```

## Launch Codex

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -Fix `
  -LaunchCodex
```
