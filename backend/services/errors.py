"""Typed LLM errors. The transient/auth split matters: transient errors
retry with backoff at the API layer; auth errors never retry; both are
distinct from the validation repair sequence in pipeline/classify.py.
"""


class LLMError(Exception):
    """Base class for all LLM-call failures."""


class TransientLLMError(LLMError):
    """429 / 5xx / timeout / connection error. Safe to retry with backoff."""


class AuthLLMError(LLMError):
    """Invalid or missing credentials. Never retried."""


class LLMProviderError(LLMError):
    """Unrecovered provider failure after retries are exhausted, or any
    non-retryable API error. Maps to error code 5001 at the API boundary."""
