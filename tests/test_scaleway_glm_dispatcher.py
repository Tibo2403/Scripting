import pytest

from litellm_scaleway_dispatching.scaleway_glm_dispatcher import (
    DEFAULT_MODEL,
    ScalewayGLMConfig,
    ScalewayGLMConfigurationError,
    dispatch_with_fallback,
    normalize_messages,
    scaleway_glm_completion,
)


def test_normalize_prompt_string():
    assert normalize_messages("hello") == [{"role": "user", "content": "hello"}]


def test_normalize_messages_keeps_chat_shape():
    messages = [{"role": "system", "content": "be concise"}, {"role": "user", "content": "ping"}]
    assert normalize_messages(messages) == messages


def test_config_requires_api_key_and_base_url():
    config = ScalewayGLMConfig(api_key=None, api_base=None)
    with pytest.raises(ScalewayGLMConfigurationError) as exc:
        config.completion_kwargs()
    assert "SCALEWAY_API_KEY" in str(exc.value)
    assert "SCALEWAY_BASE_URL" in str(exc.value)


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
        temperature=0,
    )

    assert result == {"ok": True}
    assert calls[0]["model"] == "openai/glm-test"
    assert calls[0]["api_key"] == "test-key"
    assert calls[0]["api_base"] == "https://example.invalid/v1"
    assert calls[0]["timeout"] == 12
    assert calls[0]["temperature"] == 0
    assert calls[0]["messages"] == [{"role": "user", "content": "hello"}]


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

    with pytest.raises(RuntimeError) as exc:
        dispatch_with_fallback(
            "hello",
            primary_config=config,
            fallback_models=["openai/fallback-model"],
            completion_func=fake_completion,
        )

    assert "All LiteLLM dispatch attempts failed" in str(exc.value)
