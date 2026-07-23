"""Stage 2 (normalization) + Stage 3 (PII redaction) — pure functions,
no LLM involved, so exact input/output pairs are the right kind of test."""

from pipeline.preprocess import clean_and_redact, is_long_ticket, normalize, redact_pii


def test_normalize_strips_html_and_decodes_entities():
    assert normalize("<p>Hi &amp; welcome</p>") == "Hi & welcome"


def test_normalize_cleans_markdown_but_keeps_link_text():
    assert normalize("**Bold** and [a link](https://example.com)") == "Bold and a link"


def test_normalize_collapses_whitespace():
    assert normalize("too   much\n\nwhitespace") == "too much whitespace"


def test_redact_pii_email():
    assert redact_pii("contact me at jane.doe@example.com please") == "contact me at [EMAIL] please"


def test_redact_pii_card_number():
    # 16 digits -> [CARD]
    assert redact_pii("card 4111 1111 1111 1111 was charged") == "card [CARD] was charged"


def test_redact_pii_phone_number():
    # 10 digits -> [PHONE]
    assert redact_pii("call me at 555-123-4567") == "call me at [PHONE]"


def test_redact_pii_id_like_number():
    # 5-6 digits -> [ID]
    assert redact_pii("my ticket is 48213") == "my ticket is [ID]"


def test_redact_pii_does_not_touch_short_numbers():
    # Below the 5-digit floor — not identifier-length, left alone.
    assert redact_pii("I was charged 42 dollars twice") == "I was charged 42 dollars twice"


def test_clean_and_redact_runs_normalize_before_redact():
    # HTML-wrapped email: normalize must strip the tag before redact_pii
    # ever sees the text, otherwise the tag could interfere with matching.
    text = "<b>Email me: test@example.com</b>"
    assert clean_and_redact(text) == "Email me: [EMAIL]"


def test_is_long_ticket_boundary():
    short_text = " ".join(["word"] * 300)
    long_text = " ".join(["word"] * 301)
    assert is_long_ticket(short_text, word_limit=300) is False
    assert is_long_ticket(long_text, word_limit=300) is True
