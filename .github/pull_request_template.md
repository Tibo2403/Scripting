## Summary

- 

## Validation

- [ ] Opened as a pull request before merging or pushing upstream-sensitive changes
- [ ] PowerShell syntax checked
- [ ] Bash syntax checked
- [ ] ShellCheck/PSScriptAnalyzer reviewed
- [ ] Sensitive scripts tested with `--dry-run` or `-WhatIf`
- [ ] LiteLLM routing changes ran the local dispatch smoke test without printing provider tokens

## Safety

- [ ] No credentials, tenant identifiers, scan output, packet captures, or customer data committed
- [ ] High-risk script changes keep authorization checks or dry-run behavior intact
- [ ] Live provider calls require `LITELLM_API_KEY`, `%TEMP%\codex-litellm-proxy.key`, `-ApiKey`, or explicit local-dev opt-in
