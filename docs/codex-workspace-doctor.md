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
- common generated directories already present in the project;
- possible secrets, with values intentionally hidden;
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

The JSON report includes each validation status and duration. This measures
workspace preparation and automated verification, not model quality or token
usage.

Tests and builds defined by a project can execute arbitrary repository code.
Run them only for a repository that you trust:

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -Validate `
  -AllowProjectCommands
```

## Generate Codex Guidance

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath C:\Users\user\Documents\HealthApp `
  -Fix
```

`-Fix` creates or updates a marked section in `AGENTS.md`. Existing human
instructions outside that section are preserved.

## Save a JSON Report

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -ReportPath .\codex-workspace-report.json
```

The JSON report never contains detected secret values.

## Launch Codex

```powershell
.\scripts\powershell\Optimize-CodexWorkspace.ps1 `
  -ProjectPath . `
  -Fix `
  -LaunchCodex
```
