# Security Policy

## Supported scope

Only the latest revision of the default branch is supported. Projects marked
`experimental` in `project-maturity.toml` are prototypes and may require
additional hardening before use with sensitive data, funds, or untrusted input.
Security fixes and safety improvements are accepted for administration and
authorized security-testing scripts on the current default branch.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository. Include the
affected path, reproduction steps, impact, and a minimal suggested mitigation
when possible. Do not open a public issue containing secrets, personal data,
or exploitable production details.

## Sensitive data

Do not commit credentials, API keys, tenant identifiers, scan output, packet
captures, encrypted payloads, or customer data. Use environment variables or
local-only configuration files for secrets, and redact sensitive logs before
sharing them.

## Authorized use

Scripts that perform scanning, exploitation, credential inspection, Wi-Fi
analysis, or data transfer must only be used in environments where you have
explicit permission.
