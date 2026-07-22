"""Stage 6: deterministic aggregation. Pure Python — no LLM import here,
ever (hard rule, CLAUDE.md). Aggregates the PRIMARY issue of processed
(valid) tickets only; additional_issues are never counted into headline
distributions, only into the optional urgency roll-up.

Denominator rule: every percentage divides by processed (valid) tickets,
except processing_success_rate, which divides by total_uploaded rows.
"""

from collections import Counter

from pipeline.validate import ValidationReport
from schemas.models import TicketClassification
from schemas.taxonomy import Category, Theme, Urgency


def _pct(n: int, denominator: int) -> float:
    return round(n / denominator * 100, 1) if denominator else 0.0


def count_fell_back(classifications: list[TicketClassification]) -> int:
    """Number of tickets that resolved to the fallback shape this run.
    Fallback theme is Other/Requires Human Review, and per
    Loom_Source_of_Truth.md a fallback IS the "requires human review"
    signal — same thing, counted once. A model-chosen Requires Human
    Review (rather than a system fallback) is indistinguishable by design,
    so both count the same way."""
    return sum(
        1
        for c in classifications
        if c.primary_category == Category.OTHER and c.primary_theme == Theme.REQUIRES_HUMAN_REVIEW
    )


def _theme_sentiment_avg(classifications: list[TicketClassification]) -> dict[str, float]:
    """Mean sentiment_score per primary_theme — pure Python over the
    per-ticket scores the model already returned, never a statistic the
    model itself computes (Core Principle 1). This is the "which issues
    are customers most unhappy about" signal: a theme with a very negative
    average is a priority even if its raw count isn't the highest."""
    scores_by_theme: dict[str, list[float]] = {}
    for c in classifications:
        scores_by_theme.setdefault(c.primary_theme.value, []).append(c.sentiment_score)
    return {theme: round(sum(scores) / len(scores), 1) for theme, scores in scores_by_theme.items()}


def _leaders(counts: dict) -> list[str]:
    """All keys tied for the max count, alphabetical. `Counter.most_common`
    breaks ties by insertion order, which silently crowns an arbitrary
    winner on tie-heavy data (e.g. a 9-ticket sample with 9 distinct
    themes has NO leader — every theme is tied at 1). Ties must be surfaced,
    not hidden behind whichever value happened to appear first."""
    if not counts:
        return []
    max_count = max(counts.values())
    return sorted(k for k, v in counts.items() if v == max_count)


def compute_analytics(
    classifications: list[TicketClassification], validation_report: ValidationReport
) -> dict:
    processed = len(classifications)
    total_uploaded = validation_report.total_rows

    category_counts = Counter(c.primary_category.value for c in classifications)
    theme_counts = Counter(c.primary_theme.value for c in classifications)
    sentiment_counts = Counter(c.sentiment.value for c in classifications)
    urgency_counts = Counter(c.urgency.value for c in classifications)
    actionable_count = sum(1 for c in classifications if c.actionable)

    # Optional roll-up: primary + additional_issues urgency, kept separate
    # from the headline urgency_distribution to avoid double-counting tickets.
    urgency_rollup = Counter(urgency_counts)
    for c in classifications:
        for issue in c.additional_issues:
            urgency_rollup[issue.urgency.value] += 1

    category_leaders = _leaders(category_counts)
    theme_leaders = _leaders(theme_counts)

    return {
        "total_uploaded": total_uploaded,
        "total_processed": processed,
        "total_skipped": validation_report.skipped,
        "skip_reasons": validation_report.skip_reasons,
        "processing_success_rate": _pct(processed, total_uploaded),
        "category_distribution": dict(category_counts),
        "category_distribution_pct": {k: _pct(v, processed) for k, v in category_counts.items()},
        "theme_frequency": dict(theme_counts),
        "theme_sentiment_avg": _theme_sentiment_avg(classifications),
        "sentiment_distribution": dict(sentiment_counts),
        "sentiment_distribution_pct": {k: _pct(v, processed) for k, v in sentiment_counts.items()},
        "urgency_distribution": dict(urgency_counts),
        "urgency_rollup_with_additional_issues": dict(urgency_rollup),
        "high_urgency_count": urgency_counts.get(Urgency.HIGH.value, 0),
        "actionable_count": actionable_count,
        "actionable_pct": _pct(actionable_count, processed),
        "fell_back_count": count_fell_back(classifications),
        # top_category/top_theme are only set when there is a single,
        # unambiguous leader. On a tie, they are None and the tied names
        # are listed in category_leaders/theme_leaders instead — never
        # silently pick one.
        "top_category": category_leaders[0] if len(category_leaders) == 1 else None,
        "category_leaders": category_leaders,
        "top_theme": theme_leaders[0] if len(theme_leaders) == 1 else None,
        "theme_leaders": theme_leaders,
        "top_categories": [c for c, _ in category_counts.most_common(3)],
        "top_themes": [t for t, _ in theme_counts.most_common(3)],
    }
