"""POST /analyze — the whole request/response cycle through FastAPI's
TestClient. LLMClient is monkeypatched to a FakeLLMClient (tests/conftest.py)
so no real network call or API key is ever needed. File-level validation
errors don't need the LLM at all — they reject before classification runs."""

import io

from fastapi.testclient import TestClient

from main import app
from schemas.taxonomy import Category, Sentiment, Theme, Urgency

client = TestClient(app)

VALID_RESPONSE = {
    "primary_category": Category.BILLING_PAYMENTS.value,
    "primary_theme": Theme.DUPLICATE_CHARGE.value,
    "sentiment": Sentiment.NEGATIVE.value,
    "sentiment_score": -0.7,
    "urgency": Urgency.HIGH.value,
    "actionable": True,
    "additional_issues": [],
}


def _upload(csv_text: str):
    return client.post(
        "/analyze", files={"file": ("test.csv", io.BytesIO(csv_text.encode()), "text/csv")}
    )


def test_missing_feedback_column_returns_4001():
    response = _upload("id,notes\n1,hello\n")
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == 4001


def test_empty_csv_returns_4002():
    response = _upload("feedback\n")
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == 4002


def test_all_rows_blank_returns_4003():
    # A fully blank CSV line is dropped by pandas' CSV parser itself
    # (skip_blank_lines) before it ever reaches row-level validation — an
    # explicit empty value (id present, feedback blank) is what actually
    # exercises the "valid row shape, blank feedback" 4003 path.
    response = _upload("id,feedback\n1,\n2,\n")
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == 4003


def test_successful_analysis_returns_full_payload(monkeypatch, fake_llm_client):
    fake_llm_client.structured_responses = [VALID_RESPONSE, VALID_RESPONSE]
    fake_llm_client.text_responses = ["Both tickets report duplicate billing charges."]
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)

    response = _upload(
        "id,feedback\n1,Charged twice this month.\n2,Billed twice again this cycle.\n"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["validation_report"] == {
        "total_rows": 2,
        "processed": 2,
        "skipped": 0,
        "skip_reasons": {},
        "fell_back_count": 0,
    }
    assert len(body["items"]) == 2
    assert body["items"][0]["primary_category"] == "Billing & Payments"
    assert body["analytics"]["top_category"] == "Billing & Payments"
    assert body["summary"] == "Both tickets report duplicate billing charges."


def test_skipped_rows_are_reported_but_dont_block_a_successful_response(monkeypatch, fake_llm_client):
    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)

    response = _upload("id,feedback\n1,Charged twice this month.\n2,\n")

    assert response.status_code == 200
    body = response.json()
    assert body["validation_report"]["processed"] == 1
    assert body["validation_report"]["skipped"] == 1
    assert body["validation_report"]["skip_reasons"] == {"empty_or_null_feedback": 1}
