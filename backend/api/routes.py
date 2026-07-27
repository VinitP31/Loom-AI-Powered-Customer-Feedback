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
from api.response_models import AnalyzeResponse, SkippedRowOut, ValidationReportOut
from pipeline.classify import classify_batch_streaming
from pipeline.preprocess import clean_and_redact, is_long_ticket
from pipeline.summarize import generate_executive_summary, maybe_summarize
from pipeline.validate import FileValidationError, validate_csv
from services.llm_client import LLMClient
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

        total = len(prepared)
        yield _ndjson_line({"type": "progress", "stage": "summarizing", "done": total, "total": total})
        summary = generate_executive_summary(facts, llm_client, model=config.summary_model)

        response = AnalyzeResponse(
            validation_report=ValidationReportOut(
                total_rows=report.total_rows,
                processed=report.processed,
                skipped=report.skipped,
                skip_reasons=report.skip_reasons,
                skipped_rows=[
                    SkippedRowOut(ticket_id=row.ticket_id, reason=row.reason) for row in report.skipped_rows
                ],
                fell_back_count=facts["fell_back_count"],
            ),
            items=enriched,
            analytics=facts,
            summary=summary,
        )
        yield _ndjson_line({"type": "result", "data": json.loads(response.model_dump_json())})

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
