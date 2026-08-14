# Universal review rules

These rules apply to every production code change. Report a violation only when
the changed code creates a concrete risk; do not report purely stylistic
preferences already handled by formatters or linters.

## Protect secrets and sensitive data

Never hard-code credentials, tokens, private keys, or passwords. Read secrets
from an environment variable or an approved secret store, validate that they
are present, and never include them in logs or error messages.

## Validate data at trust boundaries

Treat user input, paths, environment variables, network responses, downloaded
files, and subprocess output as untrusted. Validate required fields, types,
ranges, and allowed paths before the data reaches business logic or an
irreversible operation.

## Make failures explicit

Do not silently ignore exceptions, malformed responses, or non-zero exit codes.
Catch only failures that can be handled meaningfully, preserve useful context,
and return a non-zero process exit code when an operational script fails.

## Keep side effects safe and repeatable

Make automation idempotent where practical. Destructive actions must use an
explicit, validated target and provide a dry-run, confirmation, or force
mechanism when appropriate. Never construct executable commands from untrusted
strings.

## Test changed behavior

Every bug fix or non-trivial behavior change must include a focused automated
test, or a documented reproducible smoke test when automation is impractical.
Tests must cover the failure path that motivated the change, not only the happy
path.

## Prefer the smallest maintainable change

Reuse existing repository patterns and dependencies. Avoid duplicated logic,
unused helpers, speculative abstractions, dead branches, and unrelated cleanup.
Keep functions focused and make dependencies and configuration explicit rather
than adding mutable global state.
