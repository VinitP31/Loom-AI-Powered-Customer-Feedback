"""POST /analyze — the whole request/response cycle through FastAPI's
TestClient. LLMClient is monkeypatched to a FakeLLMClient (tests/conftest.py)
so no real network call or API key is ever needed. File-level validation
errors don't need the LLM at all — they reject before classification runs.

A successful response streams NDJSON: zero or more {"type": "progress", ...}
lines followed by exactly one {"type": "result", "data": <AnalyzeResponse>}
line — `_upload_events`/`_result_data` parse that stream so the rest of this
file can assert on the same response shape as before streaming existed."""

import io
import json

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


def _upload_events(csv_text: str) -> list[dict]:
    """For a successful (200) upload only — parses every NDJSON line."""
    response = _upload(csv_text)
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _result_data(events: list[dict]) -> dict:
    result_events = [e for e in events if e["type"] == "result"]
    assert len(result_events) == 1, "expected exactly one result event"
    return result_events[0]["data"]


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

    body = _result_data(
        _upload_events("id,feedback\n1,Charged twice this month.\n2,Billed twice again this cycle.\n")
    )

    assert body["validation_report"] == {
        "total_rows": 2,
        "processed": 2,
        "skipped": 0,
        "skip_reasons": {},
        "skipped_rows": [],
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

    body = _result_data(_upload_events("id,feedback\n1,Charged twice this month.\n2,\n"))

    assert body["validation_report"]["processed"] == 1
    assert body["validation_report"]["skipped"] == 1
    assert body["validation_report"]["skip_reasons"] == {"empty_or_null_feedback": 1}
    assert body["validation_report"]["skipped_rows"] == [{"ticket_id": "2", "reason": "empty_or_null_feedback"}]


def test_row_level_warnings_reach_the_item_not_just_the_model(monkeypatch, fake_llm_client):
    fake_llm_client.structured_responses = [VALID_RESPONSE, VALID_RESPONSE]
    fake_llm_client.text_responses = ["Both tickets report duplicate billing charges."]
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)

    body = _result_data(
        _upload_events("id,feedback\n1,Charged twice this month.\n2,Charged twice this month.\n")
    )

    assert body["items"][0]["warnings"] == []
    assert body["items"][1]["warnings"] == ["duplicate_feedback"]


def test_progress_events_stream_before_the_result_and_reach_the_total(monkeypatch, fake_llm_client):
    fake_llm_client.structured_responses = [VALID_RESPONSE, VALID_RESPONSE]
    fake_llm_client.text_responses = ["Both tickets report duplicate billing charges."]
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)

    events = _upload_events(
        "id,feedback\n1,Charged twice this month.\n2,Billed twice again this cycle.\n"
    )

    classifying = [e for e in events if e.get("stage") == "classifying"]
    summarizing = [e for e in events if e.get("stage") == "summarizing"]
    assert len(classifying) == 2, "one real progress event per ticket that finishes, not a fake timer"
    assert [e["done"] for e in classifying] == [1, 2]
    assert all(e["total"] == 2 for e in classifying)
    assert len(summarizing) == 1
    assert summarizing[0] == {"type": "progress", "stage": "summarizing", "done": 2, "total": 2}
    # Every progress event must come before the single result event.
    assert [e["type"] for e in events] == ["progress"] * 3 + ["result"]


def test_first_upload_has_no_comparison_second_upload_does(monkeypatch, fake_llm_client):
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)

    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    first = _result_data(_upload_events("id,feedback\n1,Charged twice this month.\n"))
    assert first["comparison"] is None
    assert isinstance(first["upload_id"], int)

    positive_response = {
        "primary_category": Category.USABILITY_UX.value,
        "primary_theme": Theme.POSITIVE_FEEDBACK.value,
        "sentiment": Sentiment.POSITIVE.value,
        "sentiment_score": 0.8,
        "urgency": Urgency.LOW.value,
        "actionable": False,
        "additional_issues": [],
    }
    fake_llm_client.structured_responses = [positive_response]
    fake_llm_client.text_responses = ["One glowing review."]
    second = _result_data(_upload_events("id,feedback\n1,Love the new redesign!\n"))

    assert second["upload_id"] == first["upload_id"] + 1
    assert second["comparison"] is not None
    assert second["comparison"]["previous_uploaded_at"] == first["uploaded_at"]
    assert second["comparison"]["sentiment_shift_pct"]["Positive"] == 100.0
    assert second["comparison"]["sentiment_shift_pct"]["Negative"] == -100.0
    assert second["comparison"]["new_themes"] == ["Positive Feedback"]
    assert second["comparison"]["disappeared_themes"] == ["Duplicate Charge"]
    # Before/after values, not just the bare delta — a "-100" alone doesn't
    # say what it moved from/to.
    assert second["comparison"]["sentiment_pct_before"]["Positive"] == 0.0
    assert second["comparison"]["sentiment_pct_after"]["Positive"] == 100.0
    assert second["comparison"]["actionable_pct_before"] == 100.0
    assert second["comparison"]["actionable_pct_after"] == 0.0

    # The executive summary call for the second upload must actually have
    # received the comparison data — not just computed it and thrown it away.
    second_summary_call = fake_llm_client.text_calls[-1]
    assert "comparison_to_previous_week" in second_summary_call[1]
    assert "Positive" in second_summary_call[1]
    # The first upload's summary call must NOT mention a comparison at all.
    first_summary_call = fake_llm_client.text_calls[-2]
    assert "comparison_to_previous_week" not in first_summary_call[1]

    # theme_sentiment_avg is dropped from what's sent to the summary prompt
    # entirely (not just told not to mention it) — it reads as a confusing
    # bare number ("scored a sentiment of 1.0") with no stakeholder context.
    assert "theme_sentiment_avg" not in first_summary_call[1]
    assert "theme_sentiment_avg" not in second_summary_call[1]

    # Replaying the second upload later must show the SAME comparison it
    # had live — persisted, not recomputed against whatever is "latest" at
    # replay time (there's nothing newer here, but the point is it's read
    # straight off the row, not derived).
    replay = client.get(f"/uploads/{second['upload_id']}")
    assert replay.json()["comparison"] == second["comparison"]

    # The first upload (nothing before it) has no comparison on replay either.
    first_replay = client.get(f"/uploads/{first['upload_id']}")
    assert first_replay.json()["comparison"] is None


def test_uploads_endpoints_list_and_replay_saved_snapshots(monkeypatch, fake_llm_client):
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)
    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    uploaded = _result_data(_upload_events("id,feedback\n1,Charged twice this month.\n"))

    listing = client.get("/uploads")
    assert listing.status_code == 200
    assert [row["id"] for row in listing.json()] == [uploaded["upload_id"]]
    assert listing.json()[0]["source_filename"] == "test.csv"

    replay = client.get(f"/uploads/{uploaded['upload_id']}")
    assert replay.status_code == 200
    body = replay.json()
    assert body["source_filename"] == "test.csv"
    assert body["summary"] == "One ticket processed."
    assert body["analytics"]["top_category"] == "Billing & Payments"
    # Per-ticket items are persisted too (storage/ticket_items) — replay
    # shows the same FeedbackExplorer-able data the live upload had.
    assert body["items"] == uploaded["items"]

    missing = client.get("/uploads/999999")
    assert missing.status_code == 404


def test_deleting_an_upload_also_deletes_its_ticket_items(monkeypatch, fake_llm_client):
    """ticket_items has ON DELETE CASCADE on snapshot_id — verify the rows
    are actually gone, not just unreachable via the API."""
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)
    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    uploaded = _result_data(_upload_events("id,feedback\n1,Charged twice this month.\n"))

    from storage.db import get_connection

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM ticket_items WHERE snapshot_id = %s", (uploaded["upload_id"],))
        assert cur.fetchone()[0] == 1

    assert client.delete(f"/uploads/{uploaded['upload_id']}").status_code == 204

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM ticket_items WHERE snapshot_id = %s", (uploaded["upload_id"],))
        assert cur.fetchone()[0] == 0


def test_delete_upload_removes_it_and_404s_on_repeat(monkeypatch, fake_llm_client):
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)
    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    uploaded = _result_data(_upload_events("id,feedback\n1,Charged twice this month.\n"))
    upload_id = uploaded["upload_id"]

    deleted = client.delete(f"/uploads/{upload_id}")
    assert deleted.status_code == 204

    assert client.get(f"/uploads/{upload_id}").status_code == 404
    assert [row["id"] for row in client.get("/uploads").json()] == []

    missing_delete = client.delete(f"/uploads/{upload_id}")
    assert missing_delete.status_code == 404
