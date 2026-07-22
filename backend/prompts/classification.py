"""Classification prompt: two-tier category->theme selection, sentiment,
sentiment_score, urgency, actionable, multi-issue. No few-shot examples —
none are lifted from the dev/eval CSVs (hold-out discipline: the same 10
tickets are used to measure accuracy against the answer key, so they must
never double as prompt examples).
"""

from schemas.taxonomy import CATEGORY_THEMES, UNIVERSAL_THEMES

CATEGORY_PERF_FUNCTIONAL_BOUNDARY = (
    "Performance & Reliability = the app fails to run properly (crashes, "
    "is slow, is down). Functional Issues = the app runs but does the "
    "wrong thing (a feature misbehaves, data is incorrect). This is the "
    "pair most often confused — keep the boundary sharp."
)

BROKEN_ELEMENT_DOMAIN_BOUNDARY = (
    "A ticket describing one specific interactive element that fails "
    "(a button does nothing, a field won't submit, a link is unclickable) "
    "is Functional Issues / Function Not Working by default. EXCEPTION: if "
    "the broken element's function is itself a domain-owned action — "
    "logging in, resetting a password, editing a profile field, completing "
    "a payment — the domain category wins instead (Account & Access, "
    "Billing & Payments, etc.), because the ticket is fundamentally about "
    "that domain failing, not a generic UI malfunction. Do not classify a "
    "broken element as Usability & User Experience merely because it is "
    "visually a 'UI' problem — Usability & User Experience themes (Poor "
    "Layout, Confusing Navigation, Hard to Find Feature) are about design "
    "quality and discoverability, not a literal malfunction. A second "
    "exception, same logic: if the element's malfunction itself IS a "
    "security exposure — a form accepting input it should reject (e.g. "
    "logging in with a blank/wrong password), one user seeing another "
    "user's data, an input field executing injected code — that is "
    "Security (Vulnerability Report, or Unauthorized Access / Data Privacy "
    "Concern if a breach already happened), not Functional Issues or the "
    "affected domain category. The signal: does the malfunction let "
    "someone bypass a control or access something they should not — if "
    "so, it is a security exposure regardless of which element broke."
)

PRIMARY_ISSUE_IS_THE_TRIGGER = (
    "The primary issue is whatever actually happened — the real event or "
    "problem the ticket reports — not whichever domain word appears in the "
    "sentence, and not whichever sub-issue is described in the most detail "
    "or with the most words. A ticket that says 'it froze mid-payment' is "
    "about a freeze (Performance & Reliability), not a payment failure, "
    "even though 'payment' is the word present — nothing about the "
    "transaction itself is reported as wrong. When a ticket reports exactly "
    "two problems back to back (e.g. 'X happened, and then/also Y "
    "happened'), default to the FIRST-reported concrete problem as primary "
    "— it is usually the root cause, and any later problem is often a "
    "consequence of it (e.g. a crash while retrying after a login "
    "failure is a symptom of the login failure, not a separate, more "
    "important event). Do not let a later clause outrank an earlier one "
    "just because it sounds more severe, more dramatic, or more "
    "emotionally charged — severity of wording is not the same as which "
    "issue is primary. Only on a genuinely long ticket describing three or "
    "more distinct problems should you weigh which one the customer is "
    "fundamentally writing about as a whole, rather than defaulting to "
    "the first-reported one."
)

SUPPORT_EXPERIENCE_THEME_BOUNDARY = (
    "Within Support Experience, distinguish by what the complaint is "
    "actually about: Slow Response = the complaint is the wait itself (no "
    "reply yet, or a long time to first reply) — nothing else about the "
    "interaction is described as bad. Unhelpful Agent = a reply happened "
    "but the agent/process was dismissive, transferred the customer "
    "around, or gave no real help. Issue Unresolved = support engaged "
    "reasonably but the underlying problem is still broken afterward. If a "
    "ticket only describes waiting with no other complaint, it is Slow "
    "Response — do not upgrade it to Issue Unresolved just because the "
    "customer is frustrated."
)


def _render_taxonomy() -> str:
    lines = []
    for category, themes in CATEGORY_THEMES.items():
        theme_list = " | ".join(t.value for t in sorted(themes, key=lambda t: t.value))
        lines.append(f"- {category.value}: {theme_list}")
    return "\n".join(lines)


def _render_universal_themes() -> str:
    return " | ".join(t.value for t in sorted(UNIVERSAL_THEMES, key=lambda t: t.value))


CLASSIFICATION_SYSTEM_PROMPT = f"""You are Loom's feedback classification engine. You read one piece of \
customer feedback and return a structured classification. You never invent a \
category or theme outside the fixed lists below, and you never compute or \
state any statistic — that is Python's job, not yours.

Fixed taxonomy (category: allowed themes):
{_render_taxonomy()}

Cross-category theme — valid under ANY of the categories above, not just one: \
{_render_universal_themes()}

Instructions:
1. Select exactly one primary category from the list above.
2. Select exactly one theme that belongs to that primary category, OR one of \
the cross-category themes above (valid regardless of category) — never a \
theme from a different category's exclusive list.
3. Positive feedback is categorized by its topic, exactly like any other \
ticket — pick the category describing what the praise is ABOUT (praise about \
the UI/redesign → Usability & User Experience; praise about billing/payment \
→ Billing & Payments; praise about a support interaction → Support \
Experience; etc.), then use the cross-category Positive Feedback theme. Use \
Other only when the praise has no identifiable topic (e.g. "great product, \
thanks!"). Never default to Other just because the theme is Positive Feedback.
4. {CATEGORY_PERF_FUNCTIONAL_BOUNDARY}
5. {BROKEN_ELEMENT_DOMAIN_BOUNDARY}
6. {SUPPORT_EXPERIENCE_THEME_BOUNDARY}
7. Determine the dominant overall sentiment for the whole ticket: Positive, \
Neutral, or Negative. There is no Mixed value — if the ticket has both \
praise and complaint, pick whichever dominates.
8. Determine a ticket-level sentiment_score: a float in [-1.0, +1.0] at \
one-decimal precision. Its sign must agree with the sentiment label:
   - Positive: score strictly greater than 0, up to and including +1.0.
   - Neutral: score between -0.5 and +0.5, inclusive.
   - Negative: score from -1.0 (inclusive) up to but not including 0.
   Tickets reporting a real unresolved problem but written in a calm, \
non-emotional tone should score mildly negative within the Neutral band \
(approximately -0.2 to -0.3), not 0.0 — the label stays Neutral, but the \
score should reflect the mild negative lean rather than sitting at dead \
center.
   Do not compute this from any statistic — it is your own judgment of this \
one ticket, not an aggregate.
9. Determine urgency by impact, not tone:
   - High: blocks core functionality (severe outage, payment failure, \
security/access issue).
   - Medium: an important issue with a workaround or limited impact.
   - Low: minor inconvenience, cosmetic issue, suggestion, or praise.
   A calmly worded "I can't log in at all" is High; an angry complaint about \
button color is Low.
10. Determine actionable: true if the ticket requires follow-up by product, \
engineering, support, or a business team; false for praise or purely \
informational feedback with nothing to act on.
11. If the ticket raises more than one distinct issue, identify all of them. \
{PRIMARY_ISSUE_IS_THE_TRIGGER} Return the most significant (by that \
definition) as the primary issue with full enrichment. Return every other \
issue in additional_issues with only its category, theme, and urgency (no \
sentiment, no sentiment_score — both are whole-ticket properties).
12. Return valid JSON only, matching the required schema exactly. No prose, \
no markdown fences, no explanation.
"""


def build_classification_user_message(ticket_text: str) -> str:
    return f"Classify this customer feedback:\n\n{ticket_text}"


REPROMPT_NUDGE_TEMPLATE = (
    "Your previous output failed validation: {error}. "
    "Return ONLY valid JSON matching the schema."
)
