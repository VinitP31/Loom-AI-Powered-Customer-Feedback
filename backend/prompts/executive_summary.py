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
- Write 3-6 sentences: lead with the dominant pattern, name the top \
category/theme driving it, note urgency/actionable signal if notable, and \
mention any clearly positive signal if present.
- Plain prose only. No headers, no bullet points, no JSON.
"""


def build_executive_summary_user_message(facts: dict) -> str:
    return (
        "Write the executive summary from these pre-computed facts "
        f"(JSON):\n\n{json.dumps(facts, indent=2)}"
    )
