# LLM Keys

Do not store secret values in this file. Record where each secret is stored,
who owns it, and how to rotate it.

## Key Inventory

| Secret | Storage location | Owner | Scope | Used by | Rotation date | Recovery action |
| --- | --- | --- | --- | --- | --- | --- |
| `LITELLM_API_KEY` | TBD | TBD | Local proxy access | LiteLLM clients | TBD | Regenerate local proxy key. |
| `OPENAI_API_KEY` | TBD | TBD | Approved OpenAI fallback | LiteLLM | TBD | Revoke and reissue provider key. |
| `GEMINI_API_KEY` | TBD | TBD | Approved Gemini fallback | LiteLLM | TBD | Revoke and reissue provider key. |
| Ollama access | Local machine | TBD | Local model only | Ollama | N/A | Stop service or restrict host access. |

## Storage Guidance

Local pilot:

- use session environment variables for temporary testing;
- keep local key pages outside the public repository;
- avoid writing keys to command history, screenshots, or shared notes.

Azure pilot:

- store provider keys in Azure Key Vault;
- grant access through managed identity where possible;
- record vault name, secret name, and owner in the table above.

AWS pilot:

- store provider keys in AWS Secrets Manager;
- grant access through instance roles where possible;
- record secret ARN, owner, and rotation schedule in the table above.

## Rotation Checklist

- Confirm which services use the key.
- Create or rotate the provider key.
- Update the local environment, Key Vault, or Secrets Manager value.
- Restart LiteLLM or the front router if required.
- Run the dispatch smoke test.
- Revoke the old key.
- Record the date and operator.

## Emergency Revoke

Use this when a key appears in logs, screenshots, chat history, commit history,
or shared documents:

1. Stop the local proxy or gateway.
2. Revoke the exposed key at the provider.
3. Remove the exposed value from local notes and logs when legally allowed.
4. Rotate dependent keys.
5. Run a clean smoke test with the replacement key.
6. Record the incident and corrective action in `LLM_PILOT_RESULTS.md`.
