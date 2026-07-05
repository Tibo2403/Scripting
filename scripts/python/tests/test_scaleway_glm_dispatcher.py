"""Tests for the Scaleway GLM dispatcher module (unittest-compatible)."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from litellm_scaleway_dispatching.scaleway_glm_dispatcher import (  # noqa: E402
    DEFAULT_MODEL,
    DispatchError,
    ErrorKind,
    RetryPolicy,
    ScalewayGLMConfig,
    ScalewayGLMConfigurationError,
    classify_error,
    dispatch_with_fallback,
    normalize_messages,
    scaleway_glm_completion,
)


class TestNormalizeMessages(unittest.TestCase):
    def test_normalize_prompt_string(self):
        self.assertEqual(normalize_messages(" hello "), [{"role": "user", "content": "hello"}])

    def test_normalize_rejects_empty_prompt(self):
        with self.assertRaises(ValueError):
            normalize_messages("   ")

    def test_normalize_messages_keeps_chat_shape(self):
        messages = [{"role": "system", "content": "be concise"}, {"role": "user", "content": "ping"}]
        self.assertEqual(normalize_messages(messages), messages)


class TestScalewayGLMConfig(unittest.TestCase):
    def test_config_requires_api_key_and_base_url(self):
        config = ScalewayGLMConfig(api_key=None, api_base=None)
        with self.assertRaises(ScalewayGLMConfigurationError) as ctx:
            config.completion_kwargs()
        self.assertIn("SCALEWAY_API_KEY", str(ctx.exception))
        self.assertIn("SCALEWAY_BASE_URL", str(ctx.exception))

    def test_config_rejects_non_https_base_url(self):
        config = ScalewayGLMConfig(
            api_key="test-key",
            api_base="http://example.invalid/v1",
        )
        with self.assertRaisesRegex(ScalewayGLMConfigurationError, "https"):
            config.completion_kwargs()

    def test_config_requires_v1_base_path(self):
        config = ScalewayGLMConfig(
            api_key="test-key",
            api_base="https://example.invalid",
        )
        with self.assertRaisesRegex(ScalewayGLMConfigurationError, "/v1"):
            config.completion_kwargs()

    def test_config_requires_litellm_provider_prefix(self):
        config = ScalewayGLMConfig(
            model="glm-test",
            api_key="test-key",
            api_base="https://example.invalid/v1",
        )
        with self.assertRaisesRegex(ScalewayGLMConfigurationError, "provider prefix"):
            config.completion_kwargs()

    def test_from_env_rejects_invalid_timeout(self):
        with patch.dict(os.environ, {"SCALEWAY_TIMEOUT_SECONDS": "abc"}):
            with self.assertRaisesRegex(ScalewayGLMConfigurationError, "positive integer"):
                ScalewayGLMConfig.from_env()


class TestScalewayGLMCompletion(unittest.TestCase):
    def test_completion_builds_litellm_payload_without_network_call(self):
        calls = []

        def fake_completion(**kwargs):
            calls.append(kwargs)
            return {"ok": True}

        config = ScalewayGLMConfig(
            model="openai/glm-test",
            api_key="test-key",
            api_base="https://example.invalid/v1",
            timeout_seconds=12,
        )

        result = scaleway_glm_completion(
            "hello",
            config=config,
            completion_func=fake_completion,
            retry_policy=RetryPolicy(max_retries=0),
            temperature=0,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls[0]["model"], "openai/glm-test")
        self.assertEqual(calls[0]["api_key"], "test-key")
        self.assertEqual(calls[0]["api_base"], "https://example.invalid/v1")
        self.assertEqual(calls[0]["timeout"], 12)
        self.assertEqual(calls[0]["temperature"], 0)
        self.assertEqual(calls[0]["messages"], [{"role": "user", "content": "hello"}])

    def test_completion_returns_metrics_when_requested(self):
        def fake_completion(**kwargs):
            return {"ok": True}

        config = ScalewayGLMConfig(
            model="openai/glm-test",
            api_key="test-key",
            api_base="https://example.invalid/v1",
        )

        result = scaleway_glm_completion(
            "hello",
            config=config,
            completion_func=fake_completion,
            retry_policy=RetryPolicy(max_retries=0),
            return_metrics=True,
        )

        self.assertEqual(result.response, {"ok": True})
        self.assertEqual(result.selected_model, "openai/glm-test")
        self.assertEqual(len(result.attempts), 1)
        self.assertTrue(result.attempts[0].success)
        self.assertEqual(result.attempts[0].provider, "scaleway")

    def test_retry_policy_retries_transient_errors(self):
        calls = []

        def fake_completion(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("503 service unavailable")
            return {"ok": True}

        config = ScalewayGLMConfig(
            model="openai/glm-test",
            api_key="test-key",
            api_base="https://example.invalid/v1",
        )

        result = scaleway_glm_completion(
            "hello",
            config=config,
            completion_func=fake_completion,
            retry_policy=RetryPolicy(max_retries=1, backoff_seconds=0),
            sleep_func=lambda _: None,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(calls), 2)


class TestDispatchWithFallback(unittest.TestCase):
    def test_non_retryable_auth_error_goes_to_fallback_immediately(self):
        calls = []

        def fake_completion(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("401 unauthorized")
            return {"model": kwargs["model"]}

        config = ScalewayGLMConfig(
            model=DEFAULT_MODEL,
            api_key="test-key",
            api_base="https://example.invalid/v1",
        )

        result = dispatch_with_fallback(
            "hello",
            primary_config=config,
            fallback_models=["openai/fallback-model"],
            completion_func=fake_completion,
            retry_policy=RetryPolicy(max_retries=3, backoff_seconds=0),
            sleep_func=lambda _: None,
        )

        self.assertEqual(result, {"model": "openai/fallback-model"})
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["model"], DEFAULT_MODEL)
        self.assertEqual(calls[1]["model"], "openai/fallback-model")

    def test_dispatch_uses_fallback_after_primary_failure(self):
        calls = []

        def fake_completion(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("primary down")
            return {"model": kwargs["model"]}

        config = ScalewayGLMConfig(
            model=DEFAULT_MODEL,
            api_key="test-key",
            api_base="https://example.invalid/v1",
        )

        result = dispatch_with_fallback(
            "hello",
            primary_config=config,
            fallback_models=["openai/fallback-model"],
            completion_func=fake_completion,
            retry_policy=RetryPolicy(max_retries=0),
        )

        self.assertEqual(result, {"model": "openai/fallback-model"})
        self.assertEqual(calls[0]["model"], DEFAULT_MODEL)
        self.assertEqual(calls[1]["model"], "openai/fallback-model")

    def test_dispatch_raises_when_all_attempts_fail(self):
        def fake_completion(**kwargs):
            raise RuntimeError(f"failed {kwargs['model']}")

        config = ScalewayGLMConfig(
            model="openai/glm-test",
            api_key="test-key",
            api_base="https://example.invalid/v1",
        )

        with self.assertRaises(DispatchError) as ctx:
            dispatch_with_fallback(
                "hello",
                primary_config=config,
                fallback_models=["openai/fallback-model"],
                completion_func=fake_completion,
                retry_policy=RetryPolicy(max_retries=0),
            )

        self.assertIn("All LiteLLM dispatch attempts failed", str(ctx.exception))


class TestClassifyError(unittest.TestCase):
    def test_classify_auth_error(self):
        self.assertEqual(classify_error(RuntimeError("401 unauthorized")), ErrorKind.AUTH)

    def test_classify_rate_limit_error(self):
        self.assertEqual(classify_error(RuntimeError("429 too many requests")), ErrorKind.RATE_LIMIT)

    def test_classify_timeout_error(self):
        self.assertEqual(classify_error(RuntimeError("request timeout")), ErrorKind.TIMEOUT)

    def test_classify_server_error(self):
        self.assertEqual(classify_error(RuntimeError("503 service unavailable")), ErrorKind.SERVER)

    def test_classify_bad_request_error(self):
        self.assertEqual(classify_error(RuntimeError("400 invalid model")), ErrorKind.BAD_REQUEST)

    def test_classify_unknown_error(self):
        self.assertEqual(classify_error(RuntimeError("strange failure")), ErrorKind.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
