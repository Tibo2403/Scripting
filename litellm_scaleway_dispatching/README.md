# Scaleway GLM dispatching with LiteLLM

Small isolated integration to test a Scaleway GLM provider path inside a LiteLLM dispatching project.

## What it adds

- Scaleway GLM configuration from environment variables.
- Validation for API key, model id, HTTPS base URL, `/v1` endpoint path and timeout.
- LiteLLM completion wrapper using an OpenAI-compatible provider path.
- Retry/backoff for transient errors such as rate limits, timeouts and server errors.
- Error classification for auth, rate limit, timeout, server, bad request and unknown failures.
- Fallback dispatching when the primary Scaleway GLM call fails.
- Optional dispatch metrics with latency and per-attempt status.
- Unit tests that do not call the real Scaleway API.

## Environment variables

Use these locally or as CI secrets:

- `SCALEWAY_API_KEY`
- `SCALEWAY_BASE_URL`, including the OpenAI-compatible `/v1` path
- `SCALEWAY_GLM_MODEL`, for example `openai/<scaleway-model-id>`
- `SCALEWAY_TIMEOUT_SECONDS`, optional positive integer

Do not commit real secrets.

## Example

```python
from litellm_scaleway_dispatching.scaleway_glm_dispatcher import (
    RetryPolicy,
    ScalewayGLMConfig,
    dispatch_with_fallback,
)

result = dispatch_with_fallback(
    "Return pong only.",
    primary_config=ScalewayGLMConfig.from_env(),
    fallback_models=["openai/gpt-4o-mini"],
    retry_policy=RetryPolicy(max_retries=2, backoff_seconds=0.25),
    return_metrics=True,
    temperature=0,
)

print(result.selected_model)
print(result.attempts)
```

## Run tests

```bash
python -m unittest discover -s scripts/python/tests -v
```

The tests mock the LiteLLM completion function, so they validate payload construction, retry, fallback and metrics behavior without consuming tokens.
