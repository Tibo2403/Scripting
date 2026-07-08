# Codex Installation Prompt

Codex must perform the concrete implementation steps requested by OpenClaw.

Each task must be small, testable, and reversible.

Codex must update documentation after each meaningful change.

## Constraints

- Prefer existing repository scripts and patterns.
- Do not introduce heavy dependencies.
- Do not make OpenClaw a permanent dependency.
- Run the smallest useful validation after every meaningful change.
- Preserve existing files and append documentation when possible.
- Report any failed validation with the exact command and next fix.
