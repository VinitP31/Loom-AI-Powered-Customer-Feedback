"""POST /analyze — request orchestration. Wires validate -> preprocess ->
long-ticket routing -> classify -> analytics -> executive summary into a
single stateless request/response cycle (no upload_id, no session state).

Timing itself belongs in main.py per CLAUDE.md ("time.perf_counter() at
the API boundary, not inside the pipeline") — this module only orchestrates.
"""

import io
import logging

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile

from analytics.aggregate import compute_analytics
from api.response_models import AnalyzeResponse, ValidationReportOut
from pipeline.classify import classify_batch
from pipeline.preprocess import clean_and_redact, is_long_ticket
from pipeline.summarize import generate_executive_summary, maybe_summarize
from pipeline.validate import FileValidationError, validate_csv
from services.llm_client import LLMClient
from utils.config import load_config

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile) -> AnalyzeResponse:
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

    classifications = classify_batch(
        prepared, llm_client, batch_size=config.batch_size, max_concurrency=config.max_concurrency
    )

    facts = compute_analytics(classifications, report)
    summary = generate_executive_summary(facts, llm_client, model=config.summary_model)

    return AnalyzeResponse(
        validation_report=ValidationReportOut(
            total_rows=report.total_rows,
            processed=report.processed,
            skipped=report.skipped,
            skip_reasons=report.skip_reasons,
            fell_back_count=facts["fell_back_count"],
        ),
        items=classifications,
        analytics=facts,
        summary=summary,
    )
