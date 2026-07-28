"""Direct unit tests for pipeline/summarize.py — previously only exercised
indirectly through test_api.py's success paths, which never hit the
LLMError/empty-response fallback branches or the deterministic
_fallback_summary_text tie-handling at all.
"""

from services.errors import LLMError
from pipeline.summarize import generate_executive_summary, maybe_summarize, _fallback_summary_text


def test_maybe_summarize_skips_short_tickets(fake_llm_client):
    text, was_summarized = maybe_summarize("T1", "a short ticket", is_long=False, llm_client=fake_llm_client)
    assert text == "a short ticket"
    assert was_summarized is False
    assert fake_llm_client.text_calls == []  # no call made at all for a short ticket


def test_maybe_summarize_success(fake_llm_client):
    fake_llm_client.text_responses = ["a tight summary"]
    text, was_summarized = maybe_summarize("T1", "a very long ticket " * 50, is_long=True, llm_client=fake_llm_client)
    assert text == "a tight summary"
    assert was_summarized is True


def test_maybe_summarize_falls_back_to_original_on_llm_error(fake_llm_client):
    fake_llm_client.text_responses = [LLMError("boom")]
    original = "a very long ticket " * 50
    text, was_summarized = maybe_summarize("T1", original, is_long=True, llm_client=fake_llm_client)
    assert text == original
    assert was_summarized is False


def test_maybe_summarize_falls_back_to_original_on_empty_response(fake_llm_client):
    fake_llm_client.text_responses = [""]
    original = "a very long ticket " * 50
    text, was_summarized = maybe_summarize("T1", original, is_long=True, llm_client=fake_llm_client)
    assert text == original
    assert was_summarized is False


def test_fallback_summary_text_single_leader():
    facts = {
        "total_processed": 5,
        "top_category": "Billing & Payments",
        "category_leaders": ["Billing & Payments"],
        "top_theme": "Duplicate Charge",
        "theme_leaders": ["Duplicate Charge"],
    }
    text = _fallback_summary_text(facts)
    assert "Processed 5 feedback items" in text
    assert "Top category: Billing & Payments" in text
    assert "Top theme: Duplicate Charge" in text


def test_fallback_summary_text_shows_ties_not_a_single_arbitrary_winner():
    facts = {
        "total_processed": 2,
        "top_category": None,
        "category_leaders": ["Billing & Payments", "Security"],
        "top_theme": None,
        "theme_leaders": ["App Crash", "Login Failure"],
    }
    text = _fallback_summary_text(facts)
    assert "Billing & Payments / Security (tied)" in text
    assert "App Crash / Login Failure (tied)" in text


def test_generate_executive_summary_success_passes_comparison_through(fake_llm_client):
    fake_llm_client.text_responses = ["a real narrated summary"]
    comparison = {"previous_uploaded_at": "2026-01-01T00:00:00", "sentiment_shift_pct": {"Positive": 10.0}}
    result = generate_executive_summary({"total_processed": 3}, fake_llm_client, comparison=comparison)
    assert result == "a real narrated summary"
    _system_prompt, user_message = fake_llm_client.text_calls[0]
    assert "comparison_to_previous_week" in user_message


def test_generate_executive_summary_falls_back_on_llm_error(fake_llm_client):
    fake_llm_client.text_responses = [LLMError("boom")]
    facts = {"total_processed": 5, "top_category": "Billing & Payments", "category_leaders": [], "top_theme": None, "theme_leaders": []}
    result = generate_executive_summary(facts, fake_llm_client)
    assert "Narrative summary unavailable" in result
    assert "Processed 5 feedback items" in result
