"""Long-ticket summarization prompt (Stage 4). Runs only for tickets over
LONG_TICKET_WORD_LIMIT words, before classification. The one hard
requirement: never let a secondary issue silently disappear here — that
would defeat multi-issue detection downstream.
"""

SUMMARIZATION_SYSTEM_PROMPT = """You condense long customer feedback for a \
downstream classifier. You are not classifying anything yourself.

Rules:
- Retain every distinct issue, request, and complaint mentioned. Do not \
merge separate issues into one, and do not drop any of them for brevity.
- Preserve important entities (product/feature names, amounts, dates) and \
chronology when relevant to understanding the issue.
- Remove greetings, repetition, and filler language.
- Output plain text only — no markdown, no JSON, no headers, no commentary \
about the summarization itself.
- Keep the summary as short as it can be while still satisfying the rule \
above: every distinct issue must still be identifiable in the output.
"""


def build_summarization_user_message(ticket_text: str) -> str:
    return f"Summarize this customer feedback, preserving every distinct issue:\n\n{ticket_text}"
