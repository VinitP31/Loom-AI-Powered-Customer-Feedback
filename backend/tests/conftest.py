"""Shared test fixtures. LLM_MODEL/API_KEY are required by utils.config
and by LLMClient's constructor even in tests that never make a real call
(the value is only read, never sent anywhere) — set once, autouse, so no
test needs to remember to do it."""

import pytest


@pytest.fixture(autouse=True)
def _required_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("API_KEY", "test-key")
    yield


class FakeLLMClient:
    """Duck-typed stand-in for services.llm_client.LLMClient — exposes the
    same structured_call/text_call surface classify.py and summarize.py
    call, without ever touching the network. Tests configure canned
    responses/exceptions per call via the queues below."""

    def __init__(self):
        self.structured_responses: list[dict | Exception] = []
        self.text_responses: list[str | Exception] = []
        self.structured_calls: list[tuple[str, str]] = []
        self.text_calls: list[tuple[str, str]] = []

    def structured_call(self, system_prompt, user_message, tool_name, json_schema, max_tokens=1024):
        self.structured_calls.append((system_prompt, user_message))
        response = self.structured_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def text_call(self, system_prompt, user_message, max_tokens=1024, model=None):
        self.text_calls.append((system_prompt, user_message))
        response = self.text_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def fake_llm_client() -> FakeLLMClient:
    return FakeLLMClient()
