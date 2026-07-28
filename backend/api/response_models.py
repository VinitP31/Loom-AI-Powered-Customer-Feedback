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
    upload_id: int
    uploaded_at: str
    comparison: dict | None = None


class SnapshotSummaryOut(BaseModel):
    id: int
    uploaded_at: str
    source_filename: str


class SnapshotOut(BaseModel):
    """A past upload's own dashboard, replayed read-only — including its
    per-ticket `items` (see storage/ticket_items), so the FeedbackExplorer
    table works on history replay too, same as the live dashboard.
    `comparison` is the diff AS IT WAS COMPUTED at the time (vs whatever
    was "latest" back then) — persisted, not recomputed against today's
    latest, so replaying an old week always answers "what did this look
    like against the week before it," never a moving target."""

    id: int
    uploaded_at: str
    source_filename: str
    validation_report: ValidationReportOut
    items: list[TicketClassification]
    analytics: dict
    summary: str
    comparison: dict | None = None
