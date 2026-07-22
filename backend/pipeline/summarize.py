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
    ticket_id: str, cleaned_text: str, is_long: bool, llm_client: LLMClient
) -> tuple[str, bool]:
    """Returns (text_to_classify, was_summarized). `is_long` is computed
    exactly once by the caller (pipeline.preprocess.is_long_ticket on the
    cleaned text) and reused for both the validation-report warning and
    this routing decision — this function never recomputes the word count
    itself, so the two can never disagree. If the summarization call
    itself fails, falls back to classifying the original cleaned text
    rather than dropping the ticket — summarization is a throughput
    optimization, not a correctness requirement."""
    if not is_long:
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


def _leader_text(single: str | None, tied: list[str]) -> str:
    if single:
        return single
    if tied:
        return " / ".join(tied) + " (tied)"
    return "unknown"


def _fallback_summary_text(facts: dict) -> str:
    """Deterministic, non-LLM fallback if the narration call itself fails.
    Plain restatement of the facts already computed in Python — no new
    numbers are introduced. Ties are shown as ties, never collapsed to a
    single arbitrary leader."""
    total = facts.get("total_processed", "unknown")
    top_category = _leader_text(facts.get("top_category"), facts.get("category_leaders", []))
    top_theme = _leader_text(facts.get("top_theme"), facts.get("theme_leaders", []))
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
