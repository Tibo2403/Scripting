# Scaleway GLM dispatching with LiteLLM

Small isolated integration to test a Scaleway GLM provider path inside a LiteLLM dispatching project.

## What it adds

- Scaleway GLM configuration from environment variables.
- LiteLLM completion wrapper.
- Fallback dispatching when the primary Scaleway GLM call fails.
- Unit tests that do not call the real Scaleway API.

## Environment variables

Use these locally or as CI secrets:

- SCALEWAY_API_KEY
- SCALEWAY_BASE_URL
- SCALEWAY_GLM_MODEL

Do not commit real secrets.

## Run tests

pip install pytest litellm
pytest -q tests/test_scaleway_glm_dispatcher.py

The tests mock the LiteLLM completion function, so they validate payload construction and fallback behavior without consuming tokens.
