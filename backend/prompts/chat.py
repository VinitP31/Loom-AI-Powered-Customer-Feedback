"""Chat prompt (RAG + facts). Two distinct data sources, never blended:

- `current_upload_facts` — the same Python-computed analytics/comparison
  the executive summary narrates from (see prompts/executive_summary.py).
  Real counts/percentages/top values for one specific upload (the one
  being viewed in scope="dashboard", or the most recent one in
  scope="all" — "vs previous upload" naturally means the latest upload's
  own comparison, against whichever single upload preceded it). This is
  what aggregate/statistical/comparison questions
  must be answered from.
- `retrieved_tickets` — a similarity-matched sample of individual ticket
  text (services/rag.py via storage.snapshots.search_similar_tickets).
  This is what content/specific-ticket questions must be answered from,
  cited inline.

The model never invents a number absent from `current_upload_facts`, and
never treats `retrieved_tickets` as proof of an aggregate fact (it's a
handful of similarity matches, not a count).
"""

import json

CHAT_SYSTEM_PROMPT = """You answer questions about customer feedback tickets \
for a business stakeholder. You are given up to two things: \
`current_upload_facts` (pre-computed aggregate facts — counts, \
percentages, top category/theme, and a comparison against the previous \
upload if one exists — for one specific upload) and `retrieved_tickets` \
(a handful of individual tickets whose text is similar to the question).

Rules:
- Aggregate, statistical, "top/main/biggest/most common", or \
comparison-to-previous-upload questions ("what's the top category", "what \
changed since the last upload", "which category performed better") must be \
answered ONLY from `current_upload_facts` — never from \
`retrieved_tickets`, which is just a similarity-matched sample and proves \
nothing about counts or totals. Every number you state must come \
directly from `current_upload_facts`.
- If `current_upload_facts` is missing, or doesn't contain the specific \
figure asked about (e.g. its `comparison_to_previous_week` is absent — \
meaning there's no earlier upload to compare against, or a figure was \
deliberately not included), say so plainly and point to the dashboard's \
KPI cards / "Vs Previous Upload" section instead of guessing.
- top_category/top_theme in `current_upload_facts` are only set when \
there's a single, unambiguous leader — if either is null, there was a \
tie; name the tied entries from category_leaders/theme_leaders jointly, \
never present one as if it alone won.
- Content or specific-ticket questions ("who complained about X", "what \
did people say about Y") must be answered from `retrieved_tickets` only. \
Never invent a ticket, a quote, or a detail not present in one.
- ALWAYS cite every ticket you reference in the exact format "(ticket_id)" \
— e.g. "(T007)" — immediately after mentioning it, with no other \
wrapper. This applies even when listing several tickets, one per line, \
or in a numbered list: still write "(T007)" right there, not "Ticket \
T007" or "T007:" or a bare id as a heading. This format is required \
every single time, with no exceptions, because it's how citations get \
matched back to real tickets afterward.
- A single retrieved ticket that merely mentions a topic loosely (or is \
positive/neutral feedback with no complaint in it) is not evidence of an \
"issue" — don't characterize it as one just because it was the closest \
match returned.
- When a question asks for tickets matching a specific fact you just \
answered from `current_upload_facts` (e.g. "show me tickets for the \
worst category", "which tickets are high urgency"), only cite a \
retrieved ticket whose own `category`/`sentiment`/`urgency` fields \
actually match that fact. Never cite one that contradicts it (e.g. a \
Positive-sentiment ticket as an example of "worst reviews") — if none of \
`retrieved_tickets` match, say plainly that no matching example was \
found in this sample, rather than presenting a non-matching ticket \
anyway.
- If neither source has enough information to answer, say so plainly \
rather than guessing.
- For a greeting or a question with no real connection to customer \
feedback (e.g. "hi", small talk, or something entirely unrelated), \
respond naturally and briefly — do not force a citation or discuss \
either data source at all.
- Plain prose. No headers, no JSON.
"""


def build_chat_user_message(question: str, tickets: list[dict], facts: dict | None = None) -> str:
    ticket_payload = [
        {
            "ticket_id": t["ticket_id"],
            "uploaded_at": t["uploaded_at"].isoformat(),
            "category": t["item"].get("primary_category"),
            "theme": t["item"].get("primary_theme"),
            "sentiment": t["item"].get("sentiment"),
            "urgency": t["item"].get("urgency"),
            "feedback_text": t["item"].get("feedback_text"),
        }
        for t in tickets
    ]
    payload: dict = {"question": question, "retrieved_tickets": ticket_payload}
    if facts is not None:
        # theme_sentiment_avg dropped for the same reason the executive
        # summary drops it (prompts/executive_summary.py) — a bare
        # -1.0..+1.0 score reads as meaningless/confusing in prose.
        analytics = {k: v for k, v in facts["analytics"].items() if k != "theme_sentiment_avg"}
        facts_payload = {"uploaded_at": facts["uploaded_at"].isoformat(), "analytics": analytics}
        if facts["comparison"] is not None:
            facts_payload["comparison_to_previous_week"] = facts["comparison"]
        payload["current_upload_facts"] = facts_payload
    return f"Question and data (JSON):\n{json.dumps(payload, indent=2)}"
