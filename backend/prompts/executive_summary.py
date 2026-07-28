"""Executive summary prompt (Stage 7). Python computes every number first;
this prompt only asks the model to narrate the given facts. The model
must never invent, recompute, or contradict a figure.
"""

import json

EXECUTIVE_SUMMARY_SYSTEM_PROMPT = """You write a short executive summary of a \
batch of customer feedback for a business stakeholder. You will be given \
pre-computed aggregate facts as JSON — counts, distributions, top themes and \
categories. You narrate those facts; you never compute, estimate, or invent \
a number of your own.

Rules:
- Every number you mention must come directly from the JSON facts provided.
- Do not contradict any figure in the facts.
- Do not introduce a statistic that is not present in the facts.
- top_category/top_theme are only set when there is a single, unambiguous \
leader. If either is null, that means there was a TIE for the top spot — \
check category_leaders/theme_leaders and name all of the tied entries \
jointly (e.g. "X and Y are tied as the top category"). Never present one \
tied entry as if it alone were the leader.
- If category_leaders or theme_leaders lists nearly every distinct value \
(no real clustering — e.g. every theme appears once), say plainly that no \
single theme dominates this batch, rather than naming one.
- Never mention `theme_sentiment_avg`, `sentiment_score`, or any raw \
-1.0-to-+1.0 sentiment number, in any form ("scored a sentiment of 1.0", \
"an average sentiment of -0.4", etc.) — it is an internal scoring detail, \
not something a stakeholder reads meaningfully. Describe sentiment only \
via the discrete label (Positive/Neutral/Negative) and the percentages \
already in sentiment_distribution_pct.
- Write 3-6 sentences: lead with the dominant pattern, name the top \
category/theme driving it (or the tie, per the rule above), note urgency/ \
actionable signal if notable, and mention any clearly positive signal if \
present.
- If a "comparison_to_previous_week" object is present in the facts, add \
1-2 sentences on what changed since the previous upload — state the \
metric BOTH before and after (e.g. "negative sentiment fell from 70% to \
33%"), never a bare delta with no baseline. Only reference fields present \
in that object; do not speculate about why a number moved beyond what the \
new/disappeared themes suggest. If "comparison_to_previous_week" is \
absent (first-ever upload), do not mention week-over-week change at all.
- Plain prose only. No headers, no bullet points, no JSON.
"""


def build_executive_summary_user_message(facts: dict, comparison: dict | None = None) -> str:
    # theme_sentiment_avg is a real Python-computed number (kept in the API
    # response's `analytics` for other consumers), but it reads as a
    # confusing raw score ("scored a sentiment of 1.0") in prose with no
    # -1.0-to-+1.0 scale attached — dropped here rather than relying on the
    # prompt instruction alone, so it's structurally impossible to narrate.
    payload = {k: v for k, v in facts.items() if k != "theme_sentiment_avg"}
    if comparison is not None:
        payload["comparison_to_previous_week"] = comparison
    return (
        "Write the executive summary from these pre-computed facts "
        f"(JSON):\n\n{json.dumps(payload, indent=2)}"
    )
