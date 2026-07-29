"""Unit tests for LLMClient._call_with_retry — the transient-retry vs
auth-no-retry vs generic-provider-error split. These paths were only ever
exercised indirectly through test_api.py (via FakeLLMClient, which never
touches this code at all); this file drives the real retry logic with
constructed openai SDK exceptions and a monkeypatched time.sleep so the
test suite doesn't actually sleep.
"""

import httpx
import openai
import pytest

from services.errors import AuthLLMError, LLMProviderError, TransientLLMError
from services.llm_client import LLMClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("API_KEY", "test-key")
    return LLMClient(max_retries=2, backoff_base_seconds=0)


def _fake_response(status_code: int = 429) -> httpx.Response:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return httpx.Response(status_code=status_code, request=request)


def test_transient_error_retries_then_succeeds(client, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise openai.RateLimitError("rate limited", response=_fake_response(429), body=None)
        return "ok"

    assert client._call_with_retry(flaky) == "ok"
    assert calls["n"] == 3  # failed twice, succeeded on the 3rd (max_retries=2 allows 2 retries)


def test_transient_error_exhausts_retries_and_raises_transient(client, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise openai.APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))

    with pytest.raises(TransientLLMError):
        client._call_with_retry(always_fails)
    assert calls["n"] == 3  # 1 initial attempt + 2 retries, then give up


def test_auth_error_never_retries(client, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: (_ for _ in ()).throw(AssertionError("must not sleep/retry on auth error")))
    calls = {"n": 0}

    def bad_key():
        calls["n"] += 1
        raise openai.AuthenticationError("invalid api key", response=_fake_response(401), body=None)

    with pytest.raises(AuthLLMError):
        client._call_with_retry(bad_key)
    assert calls["n"] == 1  # no retry attempted at all


def test_5xx_api_status_error_retries_like_transient(client, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = {"n": 0}

    def server_error():
        calls["n"] += 1
        if calls["n"] < 2:
            raise openai.APIStatusError("server error", response=_fake_response(503), body=None)
        return "ok"

    assert client._call_with_retry(server_error) == "ok"
    assert calls["n"] == 2


def test_4xx_api_status_error_raises_provider_error_without_retry(client, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: (_ for _ in ()).throw(AssertionError("must not retry a non-5xx status error")))
    calls = {"n": 0}

    def bad_request():
        calls["n"] += 1
        raise openai.APIStatusError("bad request", response=_fake_response(400), body=None)

    with pytest.raises(LLMProviderError):
        client._call_with_retry(bad_request)
    assert calls["n"] == 1


class _FakeEmbeddingDatum:
    def __init__(self, embedding):
        self.embedding = embedding


class _FakeEmbeddingResponse:
    def __init__(self, embeddings):
        self.data = [_FakeEmbeddingDatum(e) for e in embeddings]


def test_embed_returns_one_vector_per_text_same_order(client, monkeypatch):
    captured = {}

    def fake_create(model, input):
        captured["model"] = model
        captured["input"] = input
        return _FakeEmbeddingResponse([[0.1, 0.2], [0.3, 0.4]])

    monkeypatch.setattr(client._client.embeddings, "create", fake_create)

    result = client.embed(["first ticket", "second ticket"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["input"] == ["first ticket", "second ticket"]
    assert captured["model"] == client.embedding_model


def test_embed_empty_input_short_circuits_without_a_call(client, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("embed([]) must not make a network call")

    monkeypatch.setattr(client._client.embeddings, "create", fail_if_called)

    assert client.embed([]) == []


def test_embed_retries_transient_errors_like_other_calls(client, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = {"n": 0}

    def flaky(model, input):
        calls["n"] += 1
        if calls["n"] < 2:
            raise openai.RateLimitError("rate limited", response=_fake_response(429), body=None)
        return _FakeEmbeddingResponse([[0.5, 0.5]])

    monkeypatch.setattr(client._client.embeddings, "create", flaky)

    assert client.embed(["one ticket"]) == [[0.5, 0.5]]
    assert calls["n"] == 2
