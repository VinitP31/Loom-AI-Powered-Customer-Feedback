"""Week-over-week diff — pure Python over two already-computed `analytics`
dicts (this upload's and the previous snapshot's). No LLM involved; same
"Python computes every number" rule as the rest of analytics/. Alongside
each delta, the before/after absolute values are included too — a bare
delta ("-36.7%") is meaningless without the baseline it moved from/to
("70.0% -> 33.3%"), both for the UI and for the executive summary prompt
that reads this same dict (see prompts/executive_summary.py).
"""


def _pct_delta(current: dict[str, float], previous: dict[str, float]) -> dict[str, float]:
    keys = set(current) | set(previous)
    return {k: round(current.get(k, 0.0) - previous.get(k, 0.0), 1) for k in keys}


def _count_delta(current: dict[str, int], previous: dict[str, int]) -> dict[str, int]:
    keys = set(current) | set(previous)
    return {k: current.get(k, 0) - previous.get(k, 0) for k in keys}


def _fill_zeros(d: dict, keys: set) -> dict:
    return {k: d.get(k, 0) for k in keys}


def compute_comparison(previous: dict, current: dict) -> dict:
    previous_themes = set(previous.get("theme_frequency", {}))
    current_themes = set(current.get("theme_frequency", {}))

    sentiment_keys = set(current.get("sentiment_distribution_pct", {})) | set(previous.get("sentiment_distribution_pct", {}))
    urgency_keys = set(current.get("urgency_distribution", {})) | set(previous.get("urgency_distribution", {}))

    return {
        "previous_uploaded_at": None,  # filled in by the caller, which knows the timestamp
        "sentiment_shift_pct": _pct_delta(
            current.get("sentiment_distribution_pct", {}), previous.get("sentiment_distribution_pct", {})
        ),
        "sentiment_pct_before": _fill_zeros(previous.get("sentiment_distribution_pct", {}), sentiment_keys),
        "sentiment_pct_after": _fill_zeros(current.get("sentiment_distribution_pct", {}), sentiment_keys),
        "category_shift_pct": _pct_delta(
            current.get("category_distribution_pct", {}), previous.get("category_distribution_pct", {})
        ),
        "urgency_shift_count": _count_delta(
            current.get("urgency_distribution", {}), previous.get("urgency_distribution", {})
        ),
        "urgency_count_before": _fill_zeros(previous.get("urgency_distribution", {}), urgency_keys),
        "urgency_count_after": _fill_zeros(current.get("urgency_distribution", {}), urgency_keys),
        "new_themes": sorted(current_themes - previous_themes),
        "disappeared_themes": sorted(previous_themes - current_themes),
        "high_urgency_count_delta": current.get("high_urgency_count", 0) - previous.get("high_urgency_count", 0),
        "high_urgency_count_before": previous.get("high_urgency_count", 0),
        "high_urgency_count_after": current.get("high_urgency_count", 0),
        "actionable_pct_delta": round(current.get("actionable_pct", 0.0) - previous.get("actionable_pct", 0.0), 1),
        "actionable_pct_before": previous.get("actionable_pct", 0.0),
        "actionable_pct_after": current.get("actionable_pct", 0.0),
        "fell_back_count_delta": current.get("fell_back_count", 0) - previous.get("fell_back_count", 0),
        "fell_back_count_before": previous.get("fell_back_count", 0),
        "fell_back_count_after": current.get("fell_back_count", 0),
    }
