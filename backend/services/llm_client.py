"""LLM client wrapper. Structured output via forced function-calling (the
model must call the given function, so its reply is JSON conforming to
the function's parameters schema — no free-text parsing). Transient API
errors (429/5xx/timeout) retry with short backoff; auth errors never
retry. This is a separate concern from the validate -> coerce -> re-prompt
-> fallback sequence in pipeline/classify.py, which handles schema-
validity, not transport failures.
"""

import json
import os
import time

import openai

from services.errors import AuthLLMError, LLMProviderError, TransientLLMError

TRANSIENT_EXCEPTIONS = (
    openai.RateLimitError,
    openai.InternalServerError,
    openai.APITimeoutError,
    openai.APIConnectionError,
)


class LLMClient:
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        max_retries: int = 2,
        backoff_base_seconds: float = 0.5,
    ):
        self.model = model or os.environ["LLM_MODEL"]
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        timeout = timeout if timeout is not None else float(os.environ.get("REQUEST_TIMEOUT", 30))
        self._client = openai.OpenAI(
            api_key=api_key or os.environ["API_KEY"],
            timeout=timeout,
        )

    def _call_with_retry(self, fn):
        attempt = 0
        while True:
            try:
                return fn()
            except openai.AuthenticationError as exc:
                raise AuthLLMError(str(exc)) from exc
            except TRANSIENT_EXCEPTIONS as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise TransientLLMError(str(exc)) from exc
                time.sleep(self.backoff_base_seconds * (2 ** (attempt - 1)))
            except openai.APIStatusError as exc:
                if exc.status_code >= 500:
                    attempt += 1
                    if attempt > self.max_retries:
                        raise TransientLLMError(str(exc)) from exc
                    time.sleep(self.backoff_base_seconds * (2 ** (attempt - 1)))
                    continue
                raise LLMProviderError(str(exc)) from exc

    def structured_call(
        self,
        system_prompt: str,
        user_message: str,
        tool_name: str,
        json_schema: dict,
        max_tokens: int = 1024,
    ) -> dict:
        """Force the model to respond via a single function call matching
        json_schema. Returns the call's parsed argument dict, unvalidated
        — the caller runs it through Pydantic."""

        def _call():
            return self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": f"Return data matching the {tool_name} schema.",
                            "parameters": json_schema,
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": tool_name}},
            )

        response = self._call_with_retry(_call)
        tool_calls = response.choices[0].message.tool_calls or []
        for call in tool_calls:
            if call.function.name == tool_name:
                try:
                    return json.loads(call.function.arguments)
                except json.JSONDecodeError as exc:
                    raise LLMProviderError(f"malformed function-call arguments: {exc}") from exc
        raise LLMProviderError(f"no tool call named '{tool_name}' in response")

    def text_call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
        model: str | None = None,
    ) -> str:
        """Plain-text completion for summarization / executive summary.
        `model` overrides self.model for this call (e.g. SUMMARY_MODEL)."""

        def _call():
            return self._client.chat.completions.create(
                model=model or self.model,
                max_tokens=max_tokens,
                temperature=0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )

        response = self._call_with_retry(_call)
        return (response.choices[0].message.content or "").strip()
