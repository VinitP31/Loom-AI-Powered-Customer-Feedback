"""LLM client wrapper. Structured output via forced tool-use (the model
must call the given tool, so its reply is JSON conforming to the tool's
input_schema — no free-text parsing). Transient API errors (429/5xx/
timeout) retry with short backoff; auth errors never retry. This is a
separate concern from the validate -> coerce -> re-prompt -> fallback
sequence in pipeline/classify.py, which handles schema-validity, not
transport failures.
"""

import os
import time

import anthropic

from services.errors import AuthLLMError, LLMProviderError, TransientLLMError

TRANSIENT_EXCEPTIONS = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
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
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ["API_KEY"],
            timeout=timeout,
        )

    def _call_with_retry(self, fn):
        attempt = 0
        while True:
            try:
                return fn()
            except anthropic.AuthenticationError as exc:
                raise AuthLLMError(str(exc)) from exc
            except TRANSIENT_EXCEPTIONS as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise TransientLLMError(str(exc)) from exc
                time.sleep(self.backoff_base_seconds * (2 ** (attempt - 1)))
            except anthropic.APIStatusError as exc:
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
        """Force the model to respond via a single tool call matching
        json_schema. Returns the tool call's raw input dict, unvalidated —
        the caller runs it through Pydantic."""

        def _call():
            return self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                tools=[
                    {
                        "name": tool_name,
                        "description": f"Return data matching the {tool_name} schema.",
                        "input_schema": json_schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
            )

        response = self._call_with_retry(_call)
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input
        raise LLMProviderError(f"no tool_use block named '{tool_name}' in response")

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
            return self._client.messages.create(
                model=model or self.model,
                max_tokens=max_tokens,
                temperature=0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

        response = self._call_with_retry(_call)
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return "".join(text_blocks).strip()
