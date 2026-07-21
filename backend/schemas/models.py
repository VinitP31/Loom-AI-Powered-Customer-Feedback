"""Pydantic models for the per-ticket LLM output contract. Enums and the
category->theme map live in taxonomy.py; this module only shapes and
validates the structured object the model must return.
"""

from pydantic import BaseModel, model_validator

from schemas.taxonomy import CATEGORY_THEMES, Category, Sentiment, Theme, Urgency


def _check_theme_in_category(category: Category, theme: Theme) -> None:
    if theme not in CATEGORY_THEMES[category]:
        raise ValueError(
            f"theme '{theme.value}' does not belong to category '{category.value}'"
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


class TicketClassification(BaseModel):
    """Full per-ticket enrichment. Pure enumeration block by design —
    no free-text/reasoning field (see Loom_Source_of_Truth.md, Output
    Schema section)."""

    ticket_id: str
    primary_category: Category
    primary_theme: Theme
    sentiment: Sentiment
    urgency: Urgency
    actionable: bool
    additional_issues: list[AdditionalIssue] = []

    @model_validator(mode="after")
    def primary_theme_belongs_to_primary_category(self) -> "TicketClassification":
        _check_theme_in_category(self.primary_category, self.primary_theme)
        return self


def fallback_classification(ticket_id: str) -> TicketClassification:
    """Canonical fallback shape. Used whenever a ticket exhausts the
    validate -> coerce -> re-prompt sequence without producing a valid
    object. Never a third attempt, never an exception to the caller."""
    return TicketClassification(
        ticket_id=ticket_id,
        primary_category=Category.OTHER,
        primary_theme=Theme.UNCLEAR,
        sentiment=Sentiment.NEUTRAL,
        urgency=Urgency.LOW,
        actionable=False,
        additional_issues=[],
    )
