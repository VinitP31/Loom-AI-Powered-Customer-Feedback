"""schemas/models.py validators — theme-belongs-to-category, the
Positive Feedback cross-category exception, and the sentiment_score
sign-agreement band. These are the Pydantic-level guarantees that keep
an invented/mismatched model output from ever reaching the API response."""

import pytest
from pydantic import ValidationError

from schemas.models import ClassificationOutput, fallback_classification
from schemas.taxonomy import Category, Sentiment, Theme, Urgency


def _base_kwargs(**overrides):
    kwargs = dict(
        primary_category=Category.BILLING_PAYMENTS,
        primary_theme=Theme.DUPLICATE_CHARGE,
        sentiment=Sentiment.NEGATIVE,
        sentiment_score=-0.7,
        urgency=Urgency.HIGH,
        actionable=True,
        additional_issues=[],
    )
    kwargs.update(overrides)
    return kwargs


def test_valid_classification_passes():
    output = ClassificationOutput(**_base_kwargs())
    assert output.primary_category == Category.BILLING_PAYMENTS


def test_theme_not_owned_by_category_fails_validation():
    with pytest.raises(ValidationError):
        ClassificationOutput(
            **_base_kwargs(primary_category=Category.BILLING_PAYMENTS, primary_theme=Theme.LOGIN_FAILURE)
        )


def test_positive_feedback_theme_is_valid_under_any_category():
    for category in (Category.SECURITY, Category.OTHER, Category.SUPPORT_EXPERIENCE):
        output = ClassificationOutput(
            **_base_kwargs(
                primary_category=category,
                primary_theme=Theme.POSITIVE_FEEDBACK,
                sentiment=Sentiment.POSITIVE,
                sentiment_score=0.8,
                urgency=Urgency.LOW,
                actionable=False,
            )
        )
        assert output.primary_theme == Theme.POSITIVE_FEEDBACK


@pytest.mark.parametrize(
    "sentiment,score",
    [
        (Sentiment.POSITIVE, 0.5),
        (Sentiment.NEUTRAL, 0.0),
        (Sentiment.NEUTRAL, -0.5),
        (Sentiment.NEUTRAL, 0.5),
        (Sentiment.NEGATIVE, -0.5),
    ],
)
def test_sentiment_score_within_band_passes(sentiment, score):
    output = ClassificationOutput(**_base_kwargs(sentiment=sentiment, sentiment_score=score))
    assert output.sentiment_score == score


@pytest.mark.parametrize(
    "sentiment,score",
    [
        (Sentiment.POSITIVE, 0.0),  # Positive requires > 0, exclusive
        (Sentiment.POSITIVE, -0.1),
        (Sentiment.NEUTRAL, 0.6),  # outside [-0.5, 0.5]
        (Sentiment.NEGATIVE, 0.0),  # Negative requires < 0, exclusive
        (Sentiment.NEGATIVE, 0.1),
    ],
)
def test_sentiment_score_outside_band_fails_validation(sentiment, score):
    with pytest.raises(ValidationError):
        ClassificationOutput(**_base_kwargs(sentiment=sentiment, sentiment_score=score))


def test_additional_issue_also_enforces_theme_category_match():
    with pytest.raises(ValidationError):
        ClassificationOutput(
            **_base_kwargs(
                additional_issues=[
                    {"category": Category.SECURITY, "theme": Theme.APP_CRASH, "urgency": Urgency.MEDIUM}
                ]
            )
        )


def test_fallback_classification_shape_is_always_valid():
    fallback = fallback_classification("T-1", "some feedback text")
    assert fallback.primary_category == Category.OTHER
    assert fallback.primary_theme == Theme.REQUIRES_HUMAN_REVIEW
    assert fallback.sentiment == Sentiment.NEUTRAL
    assert fallback.sentiment_score == 0.0
    assert fallback.urgency == Urgency.LOW
    assert fallback.actionable is False
    assert fallback.additional_issues == []
