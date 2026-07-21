"""Stage 5: batch classification. One LLM call per ticket, temperature 0,
each ticket succeeding or falling back independently (batch independence —
one ticket's failure never affects another). Every response passes through
the fixed validate -> coerce -> re-prompt(x1) -> fallback sequence.
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
    object, re-parse."""
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


def _validate(raw: dict, ticket_id: str) -> tuple[TicketClassification | None, str | None]:
    try:
        output = ClassificationOutput.model_validate(raw)
    except ValidationError as exc:
        return None, str(exc)
    return TicketClassification(ticket_id=ticket_id, **output.model_dump()), None


def _safe_structured_call(llm_client: LLMClient, user_message: str) -> tuple[dict | None, str | None]:
    try:
        return llm_client.structured_call(
            CLASSIFICATION_SYSTEM_PROMPT, user_message, TOOL_NAME, _CLASSIFICATION_SCHEMA
        ), None
    except LLMError as exc:
        return None, str(exc)


def classify_ticket(ticket_id: str, cleaned_text: str, llm_client: LLMClient) -> TicketClassification:
    """Contract: repair at most once, never loop, always end in a valid
    object. Any unrecovered path — API failure or validation failure —
    ends in the fallback shape, never an exception."""
    user_message = build_classification_user_message(cleaned_text)

    raw, call_error = _safe_structured_call(llm_client, user_message)
    if call_error:
        logger.warning("ticket %s: classification call failed: %s", ticket_id, call_error)
        return fallback_classification(ticket_id)

    obj, err = _validate(raw, ticket_id)
    if obj:
        return obj

    coerced = _coerce(raw)
    if coerced is not None:
        obj, coerce_err = _validate(coerced, ticket_id)
        if obj:
            return obj
        err = coerce_err

    nudged_message = f"{user_message}\n\n{REPROMPT_NUDGE_TEMPLATE.format(error=err)}"
    raw2, call_error2 = _safe_structured_call(llm_client, nudged_message)
    if not call_error2:
        obj, _ = _validate(raw2, ticket_id)
        if obj:
            return obj

    logger.warning("ticket %s: falling back after repair sequence exhausted", ticket_id)
    return fallback_classification(ticket_id)


def classify_batch(
    tickets: list[tuple[str, str]],
    llm_client: LLMClient,
    batch_size: int = 10,
    max_concurrency: int = 5,
) -> list[TicketClassification]:
    """tickets: list of (ticket_id, cleaned_text) pairs, in the order
    results should be returned. Grouped into batches of batch_size for
    throughput bookkeeping; each batch runs with max_concurrency in-flight
    calls. classify_ticket() never raises, so one bad ticket cannot affect
    any other."""
    results: list[TicketClassification] = []
    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        for i in range(0, len(tickets), batch_size):
            chunk = tickets[i : i + batch_size]
            futures = [
                executor.submit(classify_ticket, ticket_id, text, llm_client)
                for ticket_id, text in chunk
            ]
            for ticket_id, future in zip((t[0] for t in chunk), futures):
                try:
                    results.append(future.result())
                except Exception:
                    logger.exception("ticket %s: unexpected error in batch worker", ticket_id)
                    results.append(fallback_classification(ticket_id))
    return results
