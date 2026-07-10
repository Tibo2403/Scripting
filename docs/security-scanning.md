# Security scanning

This page is the canonical entry point for the repository's defensive scanning
tools. Keep provider integration, scan execution, and validation separate:

1. `scripts/python/ai_scan_engine.py` owns reusable AI provider configuration
   and OpenAI-compatible API calls.
2. `scripts/python/ai_server_security_scan.py` owns the authorized,
   non-destructive scan workflow and evidence-grounded AI analysis.
3. `scripts/python/tests/test_ai_server_security_scan.py` validates both the
   deterministic scan behavior and engine selection without consuming API
   tokens.
4. `scripts/linux/pentest_*.sh` remains the guarded Linux pentest workflow. It
   is intentionally separate because it orchestrates external security tools.

## Fast path

Preview first:

```powershell
python .\scripts\python\ai_server_security_scan.py --target example.com --fast --dry-run --no-ai
```

Run an authorized deterministic scan:

```powershell
python .\scripts\python\ai_server_security_scan.py --target example.com --fast --yes-i-am-authorized --markdown --no-ai
```

Add GLM analysis through Z.AI:

```powershell
$env:ZAI_API_KEY = "your-z-ai-key"
python .\scripts\python\ai_server_security_scan.py --target example.com --fast --yes-i-am-authorized --markdown --ai-provider glm
```

All providers use the same evidence-grounding and independent-review pipeline.
Change providers with `--ai-provider`, or override `--ai-endpoint`,
`--ai-model`, and `--ai-api-key-env`. Reviewer overrides use the corresponding
`--ai-reviewer-*` options.

The `litellm_scaleway_dispatching/` package is a general-purpose GLM routing
experiment with retry and fallback metrics. It is not a second security
scanner; connect the security scanner to such a gateway through
`--ai-endpoint` when that deployment is required.
