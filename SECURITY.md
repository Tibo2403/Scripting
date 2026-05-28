# Security Policy

## Supported Scope

This repository contains administration and authorized security-testing scripts. Security fixes and safety improvements are accepted for the current `main` branch.

## Reporting a Vulnerability

Open a private security advisory on GitHub, or contact the repository owner directly if advisories are unavailable.

Please include:

- Affected script or workflow.
- Exact command or workflow trigger involved.
- Expected behavior and observed behavior.
- Any sensitive logs redacted before sharing.

## Sensitive Data

Do not commit credentials, API keys, tenant identifiers, scan output, packet captures, encrypted payloads, or customer data. Use environment variables or local-only configuration files for secrets.

## Authorized Use

Scripts that perform scanning, exploitation, credential inspection, Wi-Fi analysis, or data transfer must only be used in environments where you have explicit permission.
