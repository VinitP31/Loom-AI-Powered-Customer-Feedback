"""pipeline/classify.py — the validate -> coerce -> re-prompt(x1) ->
fallback sequence, using FakeLLMClient so no real network call happens.
Covers: first-try success, a malformed/no-tool-call response repaired by
the guaranteed re-prompt, and total exhaustion falling back cleanly
(never raising)."""

from schemas.taxonomy import Category, Sentiment, Theme, Urgency
from services.errors import LLMProviderError
from pipeline.classify import classify_batch, classify_ticket

VALID_RESPONSE = {
    "primary_category": Category.BILLING_PAYMENTS.value,
    "primary_theme": Theme.DUPLICATE_CHARGE.value,
    "sentiment": Sentiment.NEGATIVE.value,
    "sentiment_score": -0.7,
    "urgency": Urgency.HIGH.value,
    "actionable": True,
    "additional_issues": [],
}


def test_classify_ticket_succeeds_on_first_valid_response(fake_llm_client):
    fake_llm_client.structured_responses = [VALID_RESPONSE]
    result = classify_ticket("T-1", "text to classify", "original feedback", False, fake_llm_client)
    assert result.primary_category == Category.BILLING_PAYMENTS
    assert result.ticket_id == "T-1"
    assert result.feedback_text == "original feedback"
    assert len(fake_llm_client.structured_calls) == 1


def test_classify_ticket_recovers_via_the_one_reprompt(fake_llm_client):
    # First call: invalid enum value (fails Pydantic validation and
    # coerce can't fix a semantically wrong field). Second call (the
    # guaranteed re-prompt): valid.
    bad_response = {**VALID_RESPONSE, "primary_category": "Not A Real Category"}
    fake_llm_client.structured_responses = [bad_response, VALID_RESPONSE]
    result = classify_ticket("T-2", "text", "feedback", False, fake_llm_client)
    assert result.primary_category == Category.BILLING_PAYMENTS
    assert len(fake_llm_client.structured_calls) == 2


def test_classify_ticket_falls_back_after_reprompt_also_fails(fake_llm_client):
    bad_response = {**VALID_RESPONSE, "primary_category": "Not A Real Category"}
    fake_llm_client.structured_responses = [bad_response, bad_response]
    result = classify_ticket("T-3", "text", "original feedback", False, fake_llm_client)
    assert result.primary_category == Category.OTHER
    assert result.primary_theme == Theme.REQUIRES_HUMAN_REVIEW
    assert result.feedback_text == "original feedback"


def test_classify_ticket_falls_back_on_malformed_no_tool_call_response_too(fake_llm_client):
    # A transport-level failure (e.g. no tool call in the response) is not
    # a special case — it goes through the same coerce + one re-prompt
    # before falling back.
    fake_llm_client.structured_responses = [
        LLMProviderError("no tool call named 'emit_classification' in response"),
        LLMProviderError("no tool call named 'emit_classification' in response"),
    ]
    result = classify_ticket("T-4", "text", "feedback", False, fake_llm_client)
    assert result.primary_category == Category.OTHER
    assert result.primary_theme == Theme.REQUIRES_HUMAN_REVIEW


def test_classify_batch_preserves_order_and_ticket_independence(fake_llm_client):
    # Ticket 2 fails both attempts; tickets 1 and 3 must still succeed —
    # one bad ticket cannot affect any other (batch independence).
    bad_response = {**VALID_RESPONSE, "primary_category": "Not A Real Category"}
    fake_llm_client.structured_responses = [
        VALID_RESPONSE,  # ticket 1
        bad_response,  # ticket 2, attempt 1
        bad_response,  # ticket 2, attempt 2 (re-prompt)
        VALID_RESPONSE,  # ticket 3
    ]
    tickets = [
        ("1", "text1", "feedback1", False),
        ("2", "text2", "feedback2", False),
        ("3", "text3", "feedback3", False),
    ]
    results = classify_batch(tickets, fake_llm_client, max_concurrency=1)
    assert [r.ticket_id for r in results] == ["1", "2", "3"]
    assert results[0].primary_category == Category.BILLING_PAYMENTS
    assert results[1].primary_category == Category.OTHER  # fell back
    assert results[2].primary_category == Category.BILLING_PAYMENTS
