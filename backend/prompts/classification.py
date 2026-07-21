"""Classification prompt: two-tier category->theme selection, sentiment,
urgency, actionable, multi-issue. No few-shot examples — none are lifted
from the dev/eval CSVs (hold-out discipline: the same 10 tickets are used
to measure accuracy against the answer key, so they must never double as
prompt examples).
"""

from schemas.taxonomy import CATEGORY_THEMES

CATEGORY_PERF_FUNCTIONAL_BOUNDARY = (
    "Performance & Reliability = the app fails to run properly (crashes, "
    "is slow, is down). Functional Issues = the app runs but does the "
    "wrong thing (a feature misbehaves, data is incorrect). This is the "
    "pair most often confused — keep the boundary sharp."
)


def _render_taxonomy() -> str:
    lines = []
    for category, themes in CATEGORY_THEMES.items():
        theme_list = " | ".join(t.value for t in sorted(themes, key=lambda t: t.value))
        lines.append(f"- {category.value}: {theme_list}")
    return "\n".join(lines)


CLASSIFICATION_SYSTEM_PROMPT = f"""You are Loom's feedback classification engine. You read one piece of \
customer feedback and return a structured classification. You never invent a \
category or theme outside the fixed lists below, and you never compute or \
state any statistic — that is Python's job, not yours.

Fixed taxonomy (category: allowed themes):
{_render_taxonomy()}

Instructions:
1. Select exactly one primary category from the list above.
2. Select exactly one theme that belongs to that primary category — never a \
theme from a different category.
3. {CATEGORY_PERF_FUNCTIONAL_BOUNDARY}
4. Determine the dominant overall sentiment for the whole ticket: Positive, \
Neutral, or Negative. There is no Mixed value — if the ticket has both \
praise and complaint, pick whichever dominates.
5. Determine urgency by impact, not tone:
   - High: blocks core functionality (severe outage, payment failure, \
security/access issue).
   - Medium: an important issue with a workaround or limited impact.
   - Low: minor inconvenience, cosmetic issue, suggestion, or praise.
   A calmly worded "I can't log in at all" is High; an angry complaint about \
button color is Low.
6. Determine actionable: true if the ticket requires follow-up by product, \
engineering, support, or a business team; false for praise or purely \
informational feedback with nothing to act on.
7. If the ticket raises more than one distinct issue, identify all of them. \
Return the most significant as the primary issue with full enrichment. \
Return every other issue in additional_issues with only its category, \
theme, and urgency (no sentiment — sentiment is a whole-ticket property).
8. Return valid JSON only, matching the required schema exactly. No prose, \
no markdown fences, no explanation.
"""


def build_classification_user_message(ticket_text: str) -> str:
    return f"Classify this customer feedback:\n\n{ticket_text}"


REPROMPT_NUDGE_TEMPLATE = (
    "Your previous output failed validation: {error}. "
    "Return ONLY valid JSON matching the schema."
)
