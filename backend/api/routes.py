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

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from analytics.aggregate import compute_analytics
from api.response_models import (
    AnalyzeResponse,
    SkippedRowOut,
    SnapshotOut,
    SnapshotSummaryOut,
    ValidationReportOut,
)
from pipeline.classify import classify_batch_streaming
from pipeline.preprocess import clean_and_redact, is_long_ticket
from pipeline.summarize import generate_executive_summary, maybe_summarize
from pipeline.validate import FileValidationError, validate_csv
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
