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


def test_chat_dashboard_scope_returns_answer_and_sources(monkeypatch, fake_llm_client):
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)
    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    uploaded = _result_data(_upload_events("id,feedback\n1,Charged twice this month.\n"))

    fake_llm_client.text_responses = ["Ticket 1 is a duplicate charge complaint. (1)"]
    response = client.post(
        "/chat",
        json={"question": "What billing issues came up?", "scope": "dashboard", "snapshot_id": uploaded["upload_id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Ticket 1 is a duplicate charge complaint. (1)"
    assert [s["ticket_id"] for s in body["sources"]] == ["1"]
    assert body["sources"][0]["snapshot_id"] == uploaded["upload_id"]
    assert body["sources"][0]["source_filename"] == "test.csv"


def test_chat_dashboard_scope_requires_snapshot_id(monkeypatch, fake_llm_client):
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)

    response = client.post("/chat", json={"question": "anything", "scope": "dashboard"})

    assert response.status_code == 400


def test_chat_all_scope_searches_across_every_upload(monkeypatch, fake_llm_client):
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)
    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    first = _result_data(_upload_events("id,feedback\n1,Charged twice this month.\n"))

    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    second = _result_data(_upload_events("id,feedback\n1,Billed twice again.\n"))

    fake_llm_client.text_responses = ["Both weeks report duplicate charges. (1)"]
    response = client.post("/chat", json={"question": "duplicate charges?", "scope": "all"})

    assert response.status_code == 200
    snapshot_ids = {s["snapshot_id"] for s in response.json()["sources"]}
    assert snapshot_ids == {first["upload_id"], second["upload_id"]}


def test_chat_drops_tickets_below_the_similarity_floor(monkeypatch, fake_llm_client):
    """Unrelated tickets shouldn't be padded into `sources` just to fill
    top_k — a ticket whose embedding doesn't point the same direction as
    the question should be dropped entirely, not shown with a low score."""
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)
    fake_llm_client.structured_responses = [VALID_RESPONSE, VALID_RESPONSE]
    fake_llm_client.text_responses = ["Two tickets processed."]
    # Ingest: ticket 1's embedding points the same way the question will;
    # ticket 2's is orthogonal (similarity 0, well under the default floor).
    fake_llm_client.embed_responses = [[[1.0, 0.0], [0.0, 1.0]]]
    uploaded = _result_data(
        _upload_events("id,feedback\n1,Charged twice this month.\n2,App crashes constantly.\n")
    )

    fake_llm_client.embed_responses = [[[1.0, 0.0]]]
    fake_llm_client.text_responses = ["Ticket 1 is a duplicate charge. (1)"]
    response = client.post(
        "/chat",
        json={"question": "billing issue?", "scope": "dashboard", "snapshot_id": uploaded["upload_id"]},
    )

    assert response.status_code == 200
    sources = response.json()["sources"]
    assert [s["ticket_id"] for s in sources] == ["1"]


def test_chat_only_returns_sources_the_answer_actually_cites(monkeypatch, fake_llm_client):
    """A greeting, a refusal, or an answer that only needed one of several
    retrieved tickets shouldn't drag the rest along in `sources` as if
    they backed the answer too — only ticket ids the model actually
    wrote as "(ticket_id)" should come back."""
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)
    fake_llm_client.structured_responses = [VALID_RESPONSE, VALID_RESPONSE]
    fake_llm_client.text_responses = ["Two tickets processed."]
    uploaded = _result_data(
        _upload_events("id,feedback\n1,Charged twice this month.\n2,App crashes constantly.\n")
    )

    # Both tickets are retrieved (default fake embeddings are identical),
    # but the answer only cites one of them.
    fake_llm_client.text_responses = ["Ticket 1 is a duplicate charge. (1)"]
    response = client.post(
        "/chat",
        json={"question": "billing issue?", "scope": "dashboard", "snapshot_id": uploaded["upload_id"]},
    )
    assert [s["ticket_id"] for s in response.json()["sources"]] == ["1"]

    # A greeting cites nothing at all — sources must be empty even though
    # retrieval still ran and found candidates above the similarity floor.
    fake_llm_client.text_responses = ["Hello! How can I help you with these tickets?"]
    response = client.post(
        "/chat",
        json={"question": "hi", "scope": "dashboard", "snapshot_id": uploaded["upload_id"]},
    )
    assert response.json()["sources"] == []


def test_chat_dashboard_scope_includes_current_upload_facts(monkeypatch, fake_llm_client):
    """Aggregate questions ("top category", "what changed") need real
    computed facts, not a guess from retrieved ticket text — verify the
    chat completion call actually receives current_upload_facts."""
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)
    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    uploaded = _result_data(_upload_events("id,feedback\n1,Charged twice this month.\n"))

    fake_llm_client.text_responses = ["Top category is Billing & Payments."]
    response = client.post(
        "/chat",
        json={"question": "what is the top category?", "scope": "dashboard", "snapshot_id": uploaded["upload_id"]},
    )
    assert response.status_code == 200

    chat_call = fake_llm_client.text_calls[-1]
    assert "current_upload_facts" in chat_call[1]
    assert "Billing & Payments" in chat_call[1]
    # First-ever upload — nothing to compare against yet.
    assert "comparison_to_previous_week" not in chat_call[1]


def test_chat_includes_comparison_when_a_previous_upload_exists(monkeypatch, fake_llm_client):
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)
    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    _result_data(_upload_events("id,feedback\n1,Charged twice this month.\n"))

    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    second = _result_data(_upload_events("id,feedback\n1,Billed twice again.\n"))

    fake_llm_client.text_responses = ["Nothing changed."]
    response = client.post(
        "/chat",
        json={"question": "what changed from last week?", "scope": "dashboard", "snapshot_id": second["upload_id"]},
    )
    assert response.status_code == 200
    assert "comparison_to_previous_week" in fake_llm_client.text_calls[-1][1]


def test_chat_all_scope_uses_the_most_recent_uploads_facts(monkeypatch, fake_llm_client):
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)
    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    _result_data(_upload_events("id,feedback\n1,Charged twice this month.\n"))

    fake_llm_client.structured_responses = [VALID_RESPONSE]
    fake_llm_client.text_responses = ["One ticket processed."]
    _result_data(_upload_events("id,feedback\n1,Billed twice again.\n"))

    fake_llm_client.text_responses = ["Nothing changed."]
    response = client.post("/chat", json={"question": "what changed from last week?", "scope": "all"})
    assert response.status_code == 200
    assert "comparison_to_previous_week" in fake_llm_client.text_calls[-1][1]


def test_chat_with_no_uploads_yet_returns_friendly_message_no_sources(monkeypatch, fake_llm_client):
    monkeypatch.setattr("api.routes.LLMClient", lambda **kwargs: fake_llm_client)

    response = client.post("/chat", json={"question": "anything", "scope": "all"})

    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == []
    assert "no analyzed tickets" in body["answer"].lower()
    # No LLM call should have been made — nothing to answer from.
    assert fake_llm_client.text_calls == []


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
