"""Stage 1: file- and row-level validation. File-level problems reject the
whole upload; row-level problems skip just that row and are counted, never
raised. Skipped rows never enter analytics/KPIs — callers must read them
off ValidationReport.skipped_rows, not the valid_rows list.
"""

from dataclasses import dataclass, field

import pandas as pd

from pipeline.preprocess import has_html, has_markdown

REQUIRED_COLUMN = "feedback"


class FileValidationError(Exception):
    """File-level rejection. `code` matches the Error Codes table in
    CLAUDE.md (4001/4002/4003)."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


@dataclass
class ValidRow:
    ticket_id: str
    original_text: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class SkippedRow:
    ticket_id: str
    reason: str


@dataclass
class ValidationReport:
    total_rows: int
    valid_rows: list[ValidRow]
    skipped_rows: list[SkippedRow]

    @property
    def processed(self) -> int:
        return len(self.valid_rows)

    @property
    def skipped(self) -> int:
        return len(self.skipped_rows)

    @property
    def skip_reasons(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.skipped_rows:
            counts[row.reason] = counts.get(row.reason, 0) + 1
        return counts


def _is_blank(value) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip() == ""


def _row_ticket_id(row: pd.Series, index: int) -> str:
    raw_id = row.get("id")
    if raw_id is not None and not pd.isna(raw_id) and str(raw_id).strip():
        return str(raw_id).strip()
    return f"row-{index}"


def validate_csv(df: pd.DataFrame, long_ticket_word_limit: int) -> ValidationReport:
    if REQUIRED_COLUMN not in df.columns:
        raise FileValidationError(4001, f"missing required '{REQUIRED_COLUMN}' column")

    total_rows = len(df)
    if total_rows == 0:
        raise FileValidationError(4002, "empty file / zero data rows")

    valid_rows: list[ValidRow] = []
    skipped_rows: list[SkippedRow] = []
    seen_texts: set[str] = set()

    for index, row in df.iterrows():
        ticket_id = _row_ticket_id(row, index)
        feedback = row[REQUIRED_COLUMN]

        if _is_blank(feedback):
            skipped_rows.append(SkippedRow(ticket_id=ticket_id, reason="empty_or_null_feedback"))
            continue

        text = str(feedback)
        warnings: list[str] = []
        if has_html(text):
            warnings.append("html_present")
        if has_markdown(text):
            warnings.append("markdown_present")
        if len(text.split()) > long_ticket_word_limit:
            warnings.append("long_ticket")
        if text in seen_texts:
            warnings.append("duplicate_feedback")
        seen_texts.add(text)

        valid_rows.append(ValidRow(ticket_id=ticket_id, original_text=text, warnings=warnings))

    if not valid_rows:
        raise FileValidationError(4003, "no valid feedback found after row validation")

    return ValidationReport(total_rows=total_rows, valid_rows=valid_rows, skipped_rows=skipped_rows)
