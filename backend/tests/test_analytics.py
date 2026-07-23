"""analytics/aggregate.py — pure Python aggregation. Covers the
denominator rule (processed, not total_uploaded, except success rate),
the tie contract (top_category/top_theme null + leaders list), and
fell_back_count."""

from analytics.aggregate import compute_analytics
from pipeline.validate import SkippedRow, ValidationReport
from schemas.models import AdditionalIssue, TicketClassification, fallback_classification
from schemas.taxonomy import Category, Sentiment, Theme, Urgency


def _ticket(ticket_id, category, theme, sentiment=Sentiment.NEGATIVE, score=-0.7, urgency=Urgency.HIGH, actionable=True):
    return TicketClassification(
        ticket_id=ticket_id,
        feedback_text=f"feedback {ticket_id}",
        was_summarized=False,
        primary_category=category,
        primary_theme=theme,
        sentiment=sentiment,
        sentiment_score=score,
        urgency=urgency,
        actionable=actionable,
        additional_issues=[],
    )


def _report(total_rows, skipped_rows=None):
    return ValidationReport(total_rows=total_rows, valid_rows=[], skipped_rows=skipped_rows or [])


def test_percentages_use_processed_not_total_uploaded():
    classifications = [
        _ticket("1", Category.BILLING_PAYMENTS, Theme.DUPLICATE_CHARGE),
        _ticket("2", Category.BILLING_PAYMENTS, Theme.DUPLICATE_CHARGE),
    ]
    # 2 processed out of 10 total_rows (8 skipped) — category_distribution_pct
    # must be computed against 2, not 10.
    report = _report(total_rows=10, skipped_rows=[SkippedRow("s", "empty_or_null_feedback")] * 8)
    facts = compute_analytics(classifications, report)
    assert facts["category_distribution_pct"]["Billing & Payments"] == 100.0
    # Success rate is the one exception: processed / total_uploaded.
    assert facts["processing_success_rate"] == 20.0


def test_no_tie_sets_top_category_and_theme_directly():
    classifications = [
        _ticket("1", Category.BILLING_PAYMENTS, Theme.DUPLICATE_CHARGE),
        _ticket("2", Category.BILLING_PAYMENTS, Theme.DUPLICATE_CHARGE),
        _ticket("3", Category.SECURITY, Theme.SUSPICIOUS_ACTIVITY),
    ]
    facts = compute_analytics(classifications, _report(total_rows=3))
    assert facts["top_category"] == "Billing & Payments"
    assert facts["category_leaders"] == ["Billing & Payments"]
    assert facts["top_theme"] == "Duplicate Charge"


def test_tie_leaves_top_null_and_lists_all_leaders():
    classifications = [
        _ticket("1", Category.BILLING_PAYMENTS, Theme.DUPLICATE_CHARGE),
        _ticket("2", Category.SECURITY, Theme.SUSPICIOUS_ACTIVITY),
    ]
    facts = compute_analytics(classifications, _report(total_rows=2))
    assert facts["top_category"] is None
    assert facts["category_leaders"] == ["Billing & Payments", "Security"]
    assert facts["top_theme"] is None
    assert facts["theme_leaders"] == ["Duplicate Charge", "Suspicious Activity"]


def test_fell_back_count_matches_requires_human_review_tickets():
    classifications = [
        _ticket("1", Category.BILLING_PAYMENTS, Theme.DUPLICATE_CHARGE),
        fallback_classification("2", "unclassifiable text"),
        fallback_classification("3", "another bad one"),
    ]
    facts = compute_analytics(classifications, _report(total_rows=3))
    assert facts["fell_back_count"] == 2


def test_high_urgency_count_and_actionable_count():
    classifications = [
        _ticket("1", Category.SECURITY, Theme.SUSPICIOUS_ACTIVITY, urgency=Urgency.HIGH, actionable=True),
        _ticket("2", Category.OTHER, Theme.GENERAL_FEEDBACK, urgency=Urgency.LOW, actionable=False),
    ]
    facts = compute_analytics(classifications, _report(total_rows=2))
    assert facts["high_urgency_count"] == 1
    assert facts["actionable_count"] == 1
    assert facts["actionable_pct"] == 50.0


def test_additional_issues_are_excluded_from_headline_distributions():
    ticket = TicketClassification(
        ticket_id="1",
        feedback_text="feedback 1",
        was_summarized=False,
        primary_category=Category.BILLING_PAYMENTS,
        primary_theme=Theme.DUPLICATE_CHARGE,
        sentiment=Sentiment.NEGATIVE,
        sentiment_score=-0.7,
        urgency=Urgency.HIGH,
        actionable=True,
        additional_issues=[
            AdditionalIssue(category=Category.SECURITY, theme=Theme.SUSPICIOUS_ACTIVITY, urgency=Urgency.HIGH)
        ],
    )
    facts = compute_analytics([ticket], _report(total_rows=1))
    # Primary-only headline distribution: Security must NOT appear.
    assert "Security" not in facts["category_distribution"]
    # But the urgency rollup (which explicitly includes additional_issues)
    # does count it.
    assert facts["urgency_rollup_with_additional_issues"]["High"] == 2
