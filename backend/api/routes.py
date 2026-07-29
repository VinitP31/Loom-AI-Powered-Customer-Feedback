"""POST /analyze — request orchestration. Wires validate -> preprocess ->
long-ticket routing -> classify -> analytics -> executive summary into a
single stateless request/response cycle (no upload_id, no session state).

Streamed as newline-delimited JSON (NDJSON): one line per ticket that
finishes classification (real progress, straight off classify_batch_streaming's
as_completed loop — never a fake timer), one "summarizing" stage line, then
a final line carrying the exact same payload this endpoint used to return
in one shot. Still one POST, one request, no job_id, no polling — the
stream only exists for the lifetime of this one response.

Timing itself belongs in main.py per CLAUDE.md ("time.perf_counter() at
the API boundary, not inside the pipeline") — this module only orchestrates.
Note: main.py's timing middleware measures until the response object is
handed back, not until a streamed body finishes sending, so its logged
duration under-counts for this endpoint now — a pre-existing Starlette
streaming-response characteristic, not something patched here.
"""

import io
import json
import logging
import re

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from analytics.aggregate import compute_analytics
from api.response_models import (
    AnalyzeResponse,
    ChatRequest,
    ChatResponse,
    ChatSourceOut,
    SkippedRowOut,
    SnapshotOut,
    SnapshotSummaryOut,
    ValidationReportOut,
)
from pipeline.classify import classify_batch_streaming
from pipeline.preprocess import clean_and_redact, is_long_ticket
from pipeline.summarize import generate_executive_summary, maybe_summarize
from pipeline.validate import FileValidationError, validate_csv
from prompts.chat import CHAT_SYSTEM_PROMPT, build_chat_user_message
from services.errors import LLMError
from services.llm_client import LLMClient
from storage import snapshots
from storage.compare import compute_comparison
from utils.config import load_config

logger = logging.getLogger(__name__)

router = APIRouter()


def _ndjson_line(payload: dict) -> str:
    return json.dumps(payload) + "\n"


@router.post("/analyze")
async def analyze(file: UploadFile) -> StreamingResponse:
    config = load_config()

    raw_bytes = await file.read()
    if len(raw_bytes) > config.max_upload_size:
        raise HTTPException(
            status_code=413,
            detail=f"upload exceeds MAX_UPLOAD_SIZE ({config.max_upload_size} bytes)",
        )

    try:
        df = pd.read_csv(io.BytesIO(raw_bytes))
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail={"error_code": 4002, "message": f"could not parse CSV: {exc}"}
        ) from exc

    try:
        report = validate_csv(df)
    except FileValidationError as exc:
        raise HTTPException(
            status_code=400, detail={"error_code": exc.code, "message": exc.message}
        ) from exc

    llm_client = LLMClient(
        model=config.llm_model, api_key=config.api_key, timeout=config.request_timeout
    )

    prepared: list[tuple[str, str, str, bool]] = []
    for row in report.valid_rows:
        cleaned = clean_and_redact(row.original_text)
        # Single word-count measurement (on cleaned text) drives both the
        # long_ticket warning and the summarization-routing decision.
        if is_long_ticket(cleaned, config.long_ticket_word_limit):
            row.warnings.append("long_ticket")
        text_to_classify, was_summarized = maybe_summarize(
            row.ticket_id, cleaned, "long_ticket" in row.warnings, llm_client
        )
        prepared.append((row.ticket_id, text_to_classify, cleaned, was_summarized))

    def event_stream():
        classifications = []
        for event in classify_batch_streaming(prepared, llm_client, max_concurrency=config.max_concurrency):
            if event["type"] == "progress":
                yield _ndjson_line(
                    {"type": "progress", "stage": "classifying", "done": event["done"], "total": event["total"]}
                )
            else:
                classifications = event["results"]

        # Attach each row's validate.py quality flags (never seen by the
        # model) after classification — prepared/classifications share
        # report.valid_rows' order, so zip is safe.
        enriched = [
            c.model_copy(update={"warnings": row.warnings}) for c, row in zip(classifications, report.valid_rows)
        ]

        # One batch embedding call for the whole upload's tickets, for RAG
        # chat retrieval later. Best-effort: a failure here degrades to no
        # embeddings for this upload (chat retrieval just excludes these
        # tickets) rather than failing the whole analysis — same pattern as
        # summarization in pipeline/summarize.py.
        try:
            embeddings = llm_client.embed([item.feedback_text for item in enriched])
        except LLMError as exc:
            logger.warning("embedding call failed (%s); chat won't index this upload's tickets", exc)
            embeddings = [None] * len(enriched)

        facts = compute_analytics(enriched, report)

        # Read the previous snapshot BEFORE saving this one (so "previous"
        # never accidentally resolves to the upload currently being saved)
        # and BEFORE the summary call, so the summary can narrate the
        # week-over-week diff instead of only this upload in isolation.
        previous = snapshots.get_latest_snapshot()
        comparison = None
        if previous is not None:
            comparison = compute_comparison(previous["analytics"], facts)
            comparison["previous_uploaded_at"] = previous["uploaded_at"].isoformat()

        total = len(prepared)
        yield _ndjson_line({"type": "progress", "stage": "summarizing", "done": total, "total": total})
        summary = generate_executive_summary(facts, llm_client, model=config.summary_model, comparison=comparison)

        validation_report_out = ValidationReportOut(
            total_rows=report.total_rows,
            processed=report.processed,
            skipped=report.skipped,
            skip_reasons=report.skip_reasons,
            skipped_rows=[
                SkippedRowOut(ticket_id=row.ticket_id, reason=row.reason) for row in report.skipped_rows
            ],
            fell_back_count=facts["fell_back_count"],
        )

        saved = snapshots.save_snapshot(
            validation_report=json.loads(validation_report_out.model_dump_json()),
            analytics=facts,
            summary=summary,
            source_filename=file.filename or "upload.csv",
            items=[json.loads(item.model_dump_json()) for item in enriched],
            comparison=comparison,
            embeddings=embeddings,
        )

        response = AnalyzeResponse(
            validation_report=validation_report_out,
            items=enriched,
            analytics=facts,
            summary=summary,
            upload_id=saved["id"],
            uploaded_at=saved["uploaded_at"].isoformat(),
            comparison=comparison,
        )
        yield _ndjson_line({"type": "result", "data": json.loads(response.model_dump_json())})

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.get("/uploads")
async def list_uploads() -> list[SnapshotSummaryOut]:
    return [
        SnapshotSummaryOut(id=row["id"], uploaded_at=row["uploaded_at"].isoformat(), source_filename=row["source_filename"])
        for row in snapshots.list_snapshots()
    ]


@router.get("/uploads/{upload_id}")
async def get_upload(upload_id: int) -> SnapshotOut:
    row = snapshots.get_snapshot(upload_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no upload with id {upload_id}")
    return SnapshotOut(
        id=row["id"],
        uploaded_at=row["uploaded_at"].isoformat(),
        source_filename=row["source_filename"],
        validation_report=ValidationReportOut(**row["validation_report"]),
        items=row["items"],
        analytics=row["analytics"],
        summary=row["summary"],
        comparison=row["comparison"],
    )


@router.delete("/uploads/{upload_id}", status_code=204)
async def delete_upload(upload_id: int) -> None:
    if not snapshots.delete_snapshot(upload_id):
        raise HTTPException(status_code=404, detail=f"no upload with id {upload_id}")


@router.post("/chat")
async def chat(payload: ChatRequest) -> ChatResponse:
    """RAG + facts chat over persisted tickets. scope='dashboard' searches
    one upload's tickets; scope='all' searches every upload so far.
    Ticket ranking is a real pgvector `<=>` cosine-distance query (see
    storage.snapshots.search_similar_tickets) — no ANN index yet, exact
    scan is fine at the current handful of snapshots. Results below
    RAG_MIN_SIMILARITY are dropped entirely rather than padded out to
    top_k with unrelated tickets — can return fewer than top_k, or zero.

    Alongside ticket retrieval, `current_upload_facts` (the same
    Python-computed analytics/comparison the executive summary narrates
    from — see prompts/chat.py) is fetched for whichever upload is "this
    week": the given snapshot_id in scope='dashboard', or the most recent
    upload in scope='all' ("vs last week" naturally means the latest
    upload's own comparison). This is what makes aggregate/comparison
    questions ("top category", "what changed since last week") actually
    answerable instead of always refused — the model is told to use facts
    for those, retrieved tickets only for content questions."""
    if payload.scope == "dashboard" and payload.snapshot_id is None:
        raise HTTPException(status_code=400, detail="snapshot_id is required when scope is 'dashboard'")

    config = load_config()

    # Cheap existence check before spending an embedding call on a
    # question nothing can answer yet (e.g. no uploads at all).
    if not snapshots.list_snapshots():
        return ChatResponse(answer="No analyzed tickets are available yet to answer from.", sources=[])

    facts: snapshots.SnapshotFacts | None
    if payload.scope == "dashboard":
        facts = snapshots.get_snapshot_facts(payload.snapshot_id)  # type: ignore[arg-type]
    else:
        latest = snapshots.get_latest_snapshot()
        facts = (
            {"analytics": latest["analytics"], "comparison": latest["comparison"], "uploaded_at": latest["uploaded_at"]}
            if latest is not None
            else None
        )

    llm_client = LLMClient(
        model=config.llm_model,
        api_key=config.api_key,
        timeout=config.request_timeout,
        embedding_model=config.embedding_model,
    )

    try:
        query_embedding = llm_client.embed([payload.question])[0]
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"embedding call failed: {exc}") from exc

    top = snapshots.search_similar_tickets(
        query_embedding,
        snapshot_id=payload.snapshot_id if payload.scope == "dashboard" else None,
        top_k=config.rag_top_k,
        min_similarity=config.rag_min_similarity,
    )
    if not top and facts is None:
        return ChatResponse(
            answer="Nothing in these tickets looks related to that question.", sources=[]
        )

    try:
        answer = llm_client.text_call(CHAT_SYSTEM_PROMPT, build_chat_user_message(payload.question, top, facts))
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=f"chat call failed: {exc}") from exc

    # `sources` is what the model actually cited, not everything
    # retrieval happened to surface — a greeting, a refusal, or an answer
    # that only needed one of five retrieved tickets shouldn't drag the
    # rest along as if they backed the answer too. CHAT_SYSTEM_PROMPT
    # requires "(ticket_id)" inline, but smaller models don't always
    # comply (e.g. writing "Ticket D07:" instead) — also catch a bare
    # letter-prefixed ticket id anywhere in the text (D07, T007, W03).
    # Purely numeric ids are deliberately excluded from that fallback —
    # too likely to collide with an unrelated number in prose — so a
    # dataset using plain numeric ids still needs the parenthetical form.
    cited_ids = set(re.findall(r"\(([A-Za-z0-9_-]+)\)", answer))
    cited_ids |= set(re.findall(r"\b([A-Za-z]+\d+)\b", answer))
    cited = [t for t in top if t["ticket_id"] in cited_ids]

    return ChatResponse(
        answer=answer,
        sources=[
            ChatSourceOut(
                ticket_id=t["ticket_id"],
                snapshot_id=t["snapshot_id"],
                source_filename=t["source_filename"],
                similarity=round(t["similarity"], 3),
            )
            for t in cited
        ],
    )
