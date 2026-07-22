"""Pydantic models for the per-ticket LLM output contract. Enums and the
category->theme map live in taxonomy.py; this module only shapes and
validates the structured object the model must return.
"""

from pydantic import BaseModel, model_validator

from schemas.taxonomy import (
    CATEGORY_THEMES,
    UNIVERSAL_THEMES,
    Category,
    Sentiment,
    Theme,
    Urgency,
)


def _check_theme_in_category(category: Category, theme: Theme) -> None:
    if theme in UNIVERSAL_THEMES:
        return
    if theme not in CATEGORY_THEMES[category]:
        raise ValueError(
            f"theme '{theme.value}' does not belong to category '{category.value}'"
        )


# Sentiment -> (low, high, low_inclusive, high_inclusive) sign-agreement band.
# Positive: (0, +1] · Neutral: [-0.5, +0.5] · Negative: [-1, 0)
_SENTIMENT_SCORE_BANDS: dict[Sentiment, tuple[float, float, bool, bool]] = {
    Sentiment.POSITIVE: (0.0, 1.0, False, True),
    Sentiment.NEUTRAL: (-0.5, 0.5, True, True),
    Sentiment.NEGATIVE: (-1.0, 0.0, True, False),
}


def _check_score_matches_sentiment(sentiment: Sentiment, score: float) -> None:
    low, high, low_inclusive, high_inclusive = _SENTIMENT_SCORE_BANDS[sentiment]
    low_ok = score >= low if low_inclusive else score > low
    high_ok = score <= high if high_inclusive else score < high
    if not (low_ok and high_ok):
        band = f"{'[' if low_inclusive else '('}{low}, {high}{']' if high_inclusive else ')'}"
        raise ValueError(
            f"sentiment_score {score} does not agree with sentiment '{sentiment.value}' "
            f"(expected band {band})"
        )


class AdditionalIssue(BaseModel):
    """Secondary issue on a multi-issue ticket. No sentiment field —
    dominant sentiment is a per-ticket property, not per-issue."""

    category: Category
    theme: Theme
    urgency: Urgency

    @model_validator(mode="after")
    def theme_belongs_to_category(self) -> "AdditionalIssue":
        _check_theme_in_category(self.category, self.theme)
        return self


class ClassificationOutput(BaseModel):
    """Exactly what the LLM produces — no ticket_id, no feedback_text, no
    was_summarized. The backend attaches those; the model is never asked
    for them. This is also the shape used to build the tool's
    input_schema for structured output."""

    primary_category: Category
    primary_theme: Theme
    sentiment: Sentiment
    sentiment_score: float
    urgency: Urgency
    actionable: bool
    additional_issues: list[AdditionalIssue] = []

    @model_validator(mode="after")
    def primary_theme_belongs_to_primary_category(self) -> "ClassificationOutput":
        _check_theme_in_category(self.primary_category, self.primary_theme)
        return self

    @model_validator(mode="after")
    def sentiment_score_agrees_with_sentiment(self) -> "ClassificationOutput":
        _check_score_matches_sentiment(self.sentiment, self.sentiment_score)
        return self


class TicketClassification(ClassificationOutput):
    """Full per-ticket enrichment: ClassificationOutput plus the
    backend-attached ticket_id, feedback_text, and was_summarized. Pure
    enumeration block (plus one bounded float) by design — no free-text/
    reasoning field from the model (see Loom_Source_of_Truth.md, Output
    Schema section)."""

    ticket_id: str
    feedback_text: str
    was_summarized: bool


def fallback_classification(
    ticket_id: str, feedback_text: str, was_summarized: bool = False
) -> TicketClassification:
    """Canonical fallback shape. Used whenever a ticket exhausts the
    validate -> coerce -> re-prompt sequence without producing a valid
    object. Never a third attempt, never an exception to the caller.
    Fallback theme is Requires Human Review, not Unclear — a fallback IS
    the "requires human review" signal (see Analytics: fell_back_count)."""
    return TicketClassification(
        ticket_id=ticket_id,
        feedback_text=feedback_text,
        was_summarized=was_summarized,
        primary_category=Category.OTHER,
        primary_theme=Theme.REQUIRES_HUMAN_REVIEW,
        sentiment=Sentiment.NEUTRAL,
        sentiment_score=0.0,
        urgency=Urgency.LOW,
        actionable=False,
        additional_issues=[],
    )
