"""Response envelope for POST /analyze. Shape matches the API contract in
Loom_Source_of_Truth.md exactly: validation_report, items, analytics,
summary. Typed so FastAPI validates the outgoing payload and generates
correct OpenAPI docs.
"""

from pydantic import BaseModel

from schemas.models import TicketClassification


class SkippedRowOut(BaseModel):
    ticket_id: str
    reason: str


class ValidationReportOut(BaseModel):
    total_rows: int
    processed: int
    skipped: int
    skip_reasons: dict[str, int]
    skipped_rows: list[SkippedRowOut]
    fell_back_count: int


class AnalyzeResponse(BaseModel):
    validation_report: ValidationReportOut
    items: list[TicketClassification]
    analytics: dict
    summary: str
