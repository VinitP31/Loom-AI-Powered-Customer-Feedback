"""Stage 5: batch classification. One LLM call per ticket, temperature 0,
each ticket succeeding or falling back independently (batch independence —
one ticket's failure never affects another). Every response passes through
the fixed validate -> coerce -> re-prompt(x1) -> fallback sequence, applied
uniformly regardless of failure type (malformed JSON / no tool call included
— see _attempt_once).
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor

from pydantic import ValidationError

from prompts.classification import (
    CLASSIFICATION_SYSTEM_PROMPT,
    REPROMPT_NUDGE_TEMPLATE,
    build_classification_user_message,
)
from schemas.models import ClassificationOutput, TicketClassification, fallback_classification
from services.errors import LLMError
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)

TOOL_NAME = "emit_classification"
_CLASSIFICATION_SCHEMA = ClassificationOutput.model_json_schema()


def _coerce(raw) -> dict | None:
    """Free, no-model-call repair. With forced tool-use the SDK already
    hands back a parsed dict, so this is mostly a no-op safety net for the
    case the raw payload ever arrives as a string (e.g. a future non-tool
    code path): strip code fences, trim, extract the outermost JSON
    object, re-parse. Returns None (a safe no-op) when there's nothing to
    coerce — callers must treat that as "coercion didn't help", not as an
    error."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _validate(
    raw: dict, ticket_id: str, feedback_text: str, was_summarized: bool
) -> tuple[TicketClassification | None, str | None]:
    try:
        output = ClassificationOutput.model_validate(raw)
    except ValidationError as exc:
        return None, str(exc)
    return (
        TicketClassification(
            ticket_id=ticket_id,
            feedback_text=feedback_text,
            was_summarized=was_summarized,
            **output.model_dump(),
        ),
        None,
    )


def _safe_structured_call(llm_client: LLMClient, user_message: str) -> tuple[dict | None, str | None]:
    try:
        return llm_client.structured_call(
            CLASSIFICATION_SYSTEM_PROMPT, user_message, TOOL_NAME, _CLASSIFICATION_SCHEMA
        ), None
    except LLMError as exc:
        return None, str(exc)


def _attempt_once(
    llm_client: LLMClient,
    user_message: str,
    ticket_id: str,
    feedback_text: str,
    was_summarized: bool,
) -> tuple[TicketClassification | None, str | None]:
    """One full validate -> coerce cycle for one LLM call. A call-level
    failure (malformed JSON, no tool call, transport error) is NOT a
    special case: `raw` is simply None, coerce() harmlessly no-ops on
    None, and the call's error string is returned so the caller can feed
    it into the one guaranteed re-prompt — exactly the same path a
    schema-validation failure takes. This is what makes coerce + the one
    re-prompt apply uniformly to every failure type."""
    raw, call_error = _safe_structured_call(llm_client, user_message)
    if call_error:
        return None, call_error

    obj, err = _validate(raw, ticket_id, feedback_text, was_summarized)
    if obj:
        return obj, None

    coerced = _coerce(raw)
    if coerced is not None:
        obj, coerce_err = _validate(coerced, ticket_id, feedback_text, was_summarized)
        if obj:
            return obj, None
        err = coerce_err

    return None, err


def classify_ticket(
    ticket_id: str,
    text_to_classify: str,
    feedback_text: str,
    was_summarized: bool,
    llm_client: LLMClient,
) -> TicketClassification:
    """Contract: repair at most once, never loop, always end in a valid
    object. `text_to_classify` is what's sent to the model (the summary,
    for long tickets); `feedback_text` is always the original cleaned/
    redacted text, attached to the result regardless of what was
    classified. Any unrecovered path — API failure or validation failure,
    including malformed JSON or a missing tool call — gets coerce and the
    one guaranteed re-prompt before falling back; never an exception."""
    user_message = build_classification_user_message(text_to_classify)

    obj, err = _attempt_once(llm_client, user_message, ticket_id, feedback_text, was_summarized)
    if obj:
        return obj

    nudged_message = f"{user_message}\n\n{REPROMPT_NUDGE_TEMPLATE.format(error=err)}"
    obj, _ = _attempt_once(llm_client, nudged_message, ticket_id, feedback_text, was_summarized)
    if obj:
        return obj

    logger.warning("ticket %s: falling back after repair sequence exhausted", ticket_id)
    return fallback_classification(ticket_id, feedback_text, was_summarized)


def classify_batch(
    tickets: list[tuple[str, str, str, bool]],
    llm_client: LLMClient,
    batch_size: int = 10,
    max_concurrency: int = 5,
) -> list[TicketClassification]:
    """tickets: list of (ticket_id, text_to_classify, feedback_text,
    was_summarized) in the order results should be returned. Grouped into
    batches of batch_size for throughput bookkeeping; each batch runs with
    max_concurrency in-flight calls. classify_ticket() never raises, so
    one bad ticket cannot affect any other."""
    results: list[TicketClassification] = []
    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        for i in range(0, len(tickets), batch_size):
            chunk = tickets[i : i + batch_size]
            futures = [
                executor.submit(
                    classify_ticket, ticket_id, text, feedback_text, was_summarized, llm_client
                )
                for ticket_id, text, feedback_text, was_summarized in chunk
            ]
            for (ticket_id, _text, feedback_text, was_summarized), future in zip(chunk, futures):
                try:
                    results.append(future.result())
                except Exception:
                    logger.exception("ticket %s: unexpected error in batch worker", ticket_id)
                    results.append(fallback_classification(ticket_id, feedback_text, was_summarized))
    return results
