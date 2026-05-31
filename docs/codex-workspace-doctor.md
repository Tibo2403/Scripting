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
- the status of `AGENTS.md`.

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
