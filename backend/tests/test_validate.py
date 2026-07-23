"""Stage 1: file-level rejections (4001/4002/4003) and row-level
skip/warning behavior. No LLM involved."""

import pandas as pd
import pytest

from pipeline.validate import FileValidationError, validate_csv


def test_missing_feedback_column_rejects_with_4001():
    df = pd.DataFrame({"id": [1, 2], "notes": ["a", "b"]})
    with pytest.raises(FileValidationError) as exc_info:
        validate_csv(df)
    assert exc_info.value.code == 4001


def test_empty_dataframe_rejects_with_4002():
    df = pd.DataFrame({"feedback": []})
    with pytest.raises(FileValidationError) as exc_info:
        validate_csv(df)
    assert exc_info.value.code == 4002


def test_all_rows_empty_feedback_rejects_with_4003():
    df = pd.DataFrame({"feedback": ["", None, "   "]})
    with pytest.raises(FileValidationError) as exc_info:
        validate_csv(df)
    assert exc_info.value.code == 4003


def test_empty_rows_are_skipped_not_rejected_when_some_rows_are_valid():
    df = pd.DataFrame({"feedback": ["App crashes on launch.", "", None]})
    report = validate_csv(df)
    assert report.total_rows == 3
    assert report.processed == 1
    assert report.skipped == 2
    assert report.skip_reasons == {"empty_or_null_feedback": 2}


def test_uses_supplied_id_when_present_else_generates_stable_row_id():
    df = pd.DataFrame({"id": ["F-42", None], "feedback": ["Great app!", "Also great!"]})
    report = validate_csv(df)
    ticket_ids = [row.ticket_id for row in report.valid_rows]
    assert ticket_ids[0] == "F-42"
    assert ticket_ids[1] == "row-1"


def test_second_occurrence_of_duplicate_text_is_flagged_not_the_first():
    df = pd.DataFrame({"feedback": ["Same complaint.", "Same complaint.", "Different one."]})
    report = validate_csv(df)
    assert "duplicate_feedback" not in report.valid_rows[0].warnings
    assert "duplicate_feedback" in report.valid_rows[1].warnings
    assert "duplicate_feedback" not in report.valid_rows[2].warnings


def test_html_and_markdown_are_flagged_as_warnings_not_rejected():
    df = pd.DataFrame({"feedback": ["<b>bold</b> complaint", "**bold** complaint"]})
    report = validate_csv(df)
    assert report.processed == 2
    assert "html_present" in report.valid_rows[0].warnings
    assert "markdown_present" in report.valid_rows[1].warnings
