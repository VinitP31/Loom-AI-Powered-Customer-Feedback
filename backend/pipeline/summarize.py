"""Stage 4 (long-ticket routing) and Stage 7 (grounded executive summary).

Long-ticket routing only fires for tickets over LONG_TICKET_WORD_LIMIT
words — everything else classifies directly, so only long tickets incur
the extra call. The executive summary narrates Python-computed facts; it
never invents or contradicts a number.
"""

import logging

from prompts.executive_summary import (
    EXECUTIVE_SUMMARY_SYSTEM_PROMPT,
    build_executive_summary_user_message,
)
from prompts.summarization import (
    SUMMARIZATION_SYSTEM_PROMPT,
    build_summarization_user_message,
)
from services.errors import LLMError
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)


def maybe_summarize(
    ticket_id: str, cleaned_text: str, word_limit: int, llm_client: LLMClient
) -> tuple[str, bool]:
    """Returns (text_to_classify, was_summarized). Only calls the model
    when the ticket exceeds word_limit. If the summarization call itself
    fails, falls back to classifying the original cleaned text rather
    than dropping the ticket — summarization is a throughput optimization,
    not a correctness requirement."""
    if len(cleaned_text.split()) <= word_limit:
        return cleaned_text, False

    try:
        summary = llm_client.text_call(
            SUMMARIZATION_SYSTEM_PROMPT, build_summarization_user_message(cleaned_text)
        )
    except LLMError as exc:
        logger.warning(
            "ticket %s: summarization call failed (%s); classifying original text", ticket_id, exc
        )
        return cleaned_text, False

    if not summary:
        logger.warning("ticket %s: summarization returned empty text; classifying original", ticket_id)
        return cleaned_text, False

    return summary, True


def _fallback_summary_text(facts: dict) -> str:
    """Deterministic, non-LLM fallback if the narration call itself fails.
    Plain restatement of the facts already computed in Python — no new
    numbers are introduced."""
    total = facts.get("total_processed", "unknown")
    top_category = facts.get("top_category", "unknown")
    top_theme = facts.get("top_theme", "unknown")
    return (
        f"Processed {total} feedback items. Top category: {top_category}. "
        f"Top theme: {top_theme}. (Narrative summary unavailable — LLM call failed.)"
    )


def generate_executive_summary(facts: dict, llm_client: LLMClient, model: str | None = None) -> str:
    """facts is the Python-computed analytics aggregate — the only source
    of numbers this call is allowed to reference."""
    try:
        return llm_client.text_call(
            EXECUTIVE_SUMMARY_SYSTEM_PROMPT,
            build_executive_summary_user_message(facts),
            model=model,
        )
    except LLMError as exc:
        logger.warning("executive summary call failed (%s); using deterministic fallback", exc)
        return _fallback_summary_text(facts)
