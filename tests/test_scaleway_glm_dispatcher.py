import pytest

from litellm_scaleway_dispatching.scaleway_glm_dispatcher import (
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


def test_normalize_prompt_string():
    assert normalize_messages(" hello ") == [{"role": "user", "content": "hello"}]


def test_normalize_rejects_empty_prompt():
    with pytest.raises(ValueError):
        normalize_messages("   ")


def test_normalize_messages_keeps_chat_shape():
    messages = [{"role": "system", "content": "be concise"}, {"role": "user", "content": "ping"}]
    assert normalize_messages(messages) == messages


def test_config_requires_api_key_and_base_url():
    config = ScalewayGLMConfig(api_key=None, api_base=None)
    with pytest.raises(ScalewayGLMConfigurationError) as exc:
        config.completion_kwargs()
    assert "SCALEWAY_API_KEY" in str(exc.value)
    assert "SCALEWAY_BASE_URL" in str(exc.value)


def test_config_rejects_non_https_base_url():
    config = ScalewayGLMConfig(
        api_key="test-key",
        api_base="http://example.invalid/v1",
    )
    with pytest.raises(ScalewayGLMConfigurationError, match="https"):
        config.completion_kwargs()


def test_config_requires_v1_base_path():
    config = ScalewayGLMConfig(
        api_key="test-key",
        api_base="https://example.invalid",
    )
    with pytest.raises(ScalewayGLMConfigurationError, match="/v1"):
        config.completion_kwargs()


def test_config_requires_litellm_provider_prefix():
    config = ScalewayGLMConfig(
        model="glm-test",
        api_key="test-key",
        api_base="https://example.invalid/v1",
    )
    with pytest.raises(ScalewayGLMConfigurationError, match="provider prefix"):
        config.completion_kwargs()


def test_from_env_rejects_invalid_timeout(monkeypatch):
    monkeypatch.setenv("SCALEWAY_TIMEOUT_SECONDS", "abc")
    with pytest.raises(ScalewayGLMConfigurationError, match="positive integer"):
        ScalewayGLMConfig.from_env()


def test_completion_builds_litellm_payload_without_network_call():
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

    assert result == {"ok": True}
    assert calls[0]["model"] == "openai/glm-test"
    assert calls[0]["api_key"] == "test-key"
    assert calls[0]["api_base"] == "https://example.invalid/v1"
    assert calls[0]["timeout"] == 12
    assert calls[0]["temperature"] == 0
    assert calls[0]["messages"] == [{"role": "user", "content": "hello"}]


def test_completion_returns_metrics_when_requested():
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

    assert result.response == {"ok": True}
    assert result.selected_model == "openai/glm-test"
    assert len(result.attempts) == 1
    assert result.attempts[0].success is True
    assert result.attempts[0].provider == "scaleway"


def test_retry_policy_retries_transient_errors():
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

    assert result == {"ok": True}
    assert len(calls) == 2


def test_non_retryable_auth_error_goes_to_fallback_immediately():
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

    assert result == {"model": "openai/fallback-model"}
    assert len(calls) == 2
    assert calls[0]["model"] == DEFAULT_MODEL
    assert calls[1]["model"] == "openai/fallback-model"


def test_dispatch_uses_fallback_after_primary_failure():
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

    assert result == {"model": "openai/fallback-model"}
    assert calls[0]["model"] == DEFAULT_MODEL
    assert calls[1]["model"] == "openai/fallback-model"


def test_dispatch_raises_when_all_attempts_fail():
    def fake_completion(**kwargs):
        raise RuntimeError(f"failed {kwargs['model']}")

    config = ScalewayGLMConfig(
        model="openai/glm-test",
        api_key="test-key",
        api_base="https://example.invalid/v1",
    )

    with pytest.raises(DispatchError) as exc:
        dispatch_with_fallback(
            "hello",
            primary_config=config,
            fallback_models=["openai/fallback-model"],
            completion_func=fake_completion,
            retry_policy=RetryPolicy(max_retries=0),
        )

    assert "All LiteLLM dispatch attempts failed" in str(exc.value)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("401 unauthorized", ErrorKind.AUTH),
        ("429 too many requests", ErrorKind.RATE_LIMIT),
        ("request timeout", ErrorKind.TIMEOUT),
        ("503 service unavailable", ErrorKind.SERVER),
        ("400 invalid model", ErrorKind.BAD_REQUEST),
        ("strange failure", ErrorKind.UNKNOWN),
    ],
)
def test_classify_error(message, expected):
    assert classify_error(RuntimeError(message)) == expected
