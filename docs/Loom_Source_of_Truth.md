# Loom — Source of Truth: Technical Design & Architecture

> Loom (formerly PulseAI) is the single source of truth for design, schema, and implementation decisions. Where code and this document disagree, this document wins unless a decision is explicitly revised here.

---

## Executive Summary

Loom is an AI-powered customer feedback analysis platform. It converts raw, free-text customer feedback into structured, consistent, business-ready insight: per-ticket classification, sentiment and urgency scoring, theme classification, aggregate analytics, a grounded narrative summary, and an interactive dashboard.

The architecture deliberately separates deterministic software from AI reasoning. Python performs validation, cleaning, aggregation, and all numeric computation. The LLM is used only where genuine language understanding is required: classifying each ticket, and narrating pre-computed numbers into a readable summary. This keeps the system consistent, cost-efficient, testable, and extensible.

---

## Core Principles

These are governing constraints. Every implementation decision must be consistent with them.

1. **The LLM classifies and phrases; Python computes everything numeric.** The model never counts, sums, or calculates percentages. All arithmetic is deterministic Python over validated data.
2. **Structured output only.** Every LLM response conforms to a fixed schema and is validated before use. No free-text parsing.
3. **Closed vocabularies.** Categories, themes, sentiment, and urgency are fixed enumerations. The model selects from known values; it never invents labels.
4. **Determinism by construction.** Temperature 0, discrete outputs, and closed lists make the same input produce the same output — without relying on a cache.
5. **Validate before AI.** Deterministic checks reject or repair bad input before any token reaches the model.
6. **Never crash the batch.** Every enrichment is validated, repaired once, and falls back to a valid schema shape on failure. One bad ticket must not fail the run.
7. **The dashboard never calls the LLM.** AI runs once during processing and writes structured results. The dashboard reads processed data only.
8. **Simplicity over speculative production complexity.** Build what the scope needs; document deferred capability as a clean extension path.

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | React + TypeScript | Modular, type-safe UI |
| UI system | Tailwind CSS + shadcn/ui | Consistent design primitives |
| Charts | Recharts | Declarative dashboard visualizations |
| Backend | FastAPI | Async APIs, automatic OpenAPI |
| Validation | Pydantic | Type-safe schema enforcement and repair |
| Data handling | Pandas | CSV parsing and tabular processing |
| AI | LLM API | Semantic classification, narration, chat, and embeddings |
| Persistence | Postgres + `pgvector` | Multi-week snapshots, per-ticket embeddings, RAG chat retrieval |

---

## High-Level Architecture

```text
                         +----------------------+
                         |   React Dashboard    |
                         |  (+ History Sidebar) |
                         +----------+-----------+
                                    |
                               REST API
                                    |
                    +---------------v---------------+
                    |        FastAPI Backend        |
                    +---------------+---------------+
                                    |
     +------------------+-----------+-----------+------------------+
     |                  |                       |                  |
     v                  v                       v                  v
+-----------+   +----------------+     +----------------+   +-------------+
| Validation|-->| Preprocessing  |---->|  AI Pipeline   |-->| Analytics   |
| Layer     |   | (clean + PII)  |     | (batch LLM)    |   | Engine      |
+-----------+   +----------------+     +-------+--------+   +------+------+
                                               |                   |
                                               +---------+---------+
                                                         |
                                                  Structured JSON
                                                         |
                                              Executive Summary (LLM)
                                              (narrates vs-last-week
                                               diff too, when one exists)
                                                         |
                                                 Dashboard Response
                                                         |
                                                         v
                                          +--------------------------+
                                          |   Postgres (storage/)    |
                                          | analysis_snapshots       |
                                          | ticket_items (+embedding)|
                                          +-------------+------------+
                                                         ^
                                                         |
                                          +--------------+------------+
                                          |     POST /chat            |
                                          | embed question (LLM)      |
                                          | pgvector <=> search       |
                                          | + current_upload_facts    |
                                          | -> one grounded LLM reply |
                                          +---------------------------+
                                                         ^
                                                         |
                                          React "Chat with Tickets"
                                            widget (Morphing Orb)
```

Every `/analyze` run persists its result (aggregate snapshot + per-ticket items + the week-over-week diff, all computed above) to Postgres before responding — this is a write on the way out, not a second request. See **Multi-Week Persistence** below for the full contract. Each ticket's redacted text is also embedded at that point and stored in `ticket_items.embedding` (a real `pgvector` column) — this is what the RAG chat feature (**Chat with Tickets**, below) searches over. `POST /chat` is a separate, later request, independent of `/analyze`.

---

## End-to-End Flow

```text
CSV Upload
   │
   ▼
Validation            reject invalid file; skip empty/null rows (counted)
   │
   ▼
Normalization         strip HTML/markdown, unicode + whitespace cleanup
   │
   ▼
PII Redaction         regex redaction before any text reaches the model
   │
   ▼
Long-Ticket Routing   > 300 words → summarization prompt → classification
   │                  otherwise   → classification directly
   ▼
Concurrency Pool      submit all tickets; concurrency cap bounds in-flight calls
   │
   ▼
LLM Classification    temp 0, one call per ticket, structured JSON
   │                  validate → repair once → fallback shape on failure
   ▼
Python Analytics      counts, distributions, theme frequency, KPIs
   │
   ▼
Executive Summary     Python builds number-facts → one LLM call narrates
   │
   ▼
API Response          structured items + analytics + summary + report
   │
   ▼
Dashboard             KPI cards, charts, feedback explorer (reads only)
```

The shape to keep in mind: **AI at the two ends, deterministic Python in the middle, every countable value closed-list or computed.**

---

## Processing Pipeline

**Pipeline invariant:** every ticket that enters classification must leave with a valid schema object, even if AI processing fails. There is no code path that emits a partial, null, or malformed classification — failure produces the fallback shape (below), never an exception that halts the run.

**Skipped-row invariant:** rows rejected during validation are reported separately and are **never** included in KPI calculations, distributions, or any dashboard metric. Skipped rows count toward the upload total and the processing-success rate only.

### Stage 1 — Validation

Reject invalid uploads before any AI processing. Skip bad rows without failing the run.

**File-level errors (reject upload):**
- Missing `feedback` column
- Empty file / zero data rows

**Row-level (skip row, increment skipped count):**
- Empty feedback
- Null / NaN feedback

**Warnings (process, but flag):**
- HTML detected
- Markdown detected
- Very long feedback (> 300 words → routed to long-ticket handling)
- Duplicate feedback (processed independently; flagged only — the 2nd-and-later occurrence of a repeated text is flagged, the first occurrence is not)

### Stage 2 — Normalization

Deterministic Python cleanup:
- HTML stripping and entity decoding
- Markdown cleanup
- Unicode normalization
- Whitespace normalization
- Optional URL removal — config-gated (`strip_urls`), default off

### Stage 3 — PII Redaction

Regex-based redaction applied **before any text reaches the model**. This is a required stage, enabled by default: no raw customer-identifying data is sent to the LLM. It is a genuine production and data-minimization requirement, not cosmetic cleanup.

Redact: email addresses, phone numbers, card-like numeric sequences, and numeric ID-length sequences. Replace with typed placeholders (`[EMAIL]`, `[PHONE]`, `[CARD]`, `[ID]`) so the model retains context that *a* value was present without seeing it.

**Honest note on the `[ID]` heuristic:** it is a digit-length heuristic (5–6 digit runs), not true ID-pattern matching (no prefix/format awareness). It can false-positive on incidental 5–6 digit numbers that aren't identifiers at all (an amount, a date-like number). A 7-12 digit non-phone identifier (e.g. an invoice number) is similarly mislabeled `[PHONE]`. Accepted as a reasonable approximation, not a precise pattern matcher. The digit-run regex does include parentheses in its character class specifically so a parenthesized area code, e.g. `(555) 123-4567`, is consumed as one run and fully redacted — an earlier version without parentheses left the area code un-redacted, a real leak rather than a labeling nuance, fixed once found.

### Stage 4 — Long-Ticket Routing

If a ticket exceeds **300 words**, it is first passed through a **summarization prompt**, and the summary is then classified. Otherwise it is classified directly.

```text
Long ticket ( >300 words )  → Summarization Prompt → Classification Prompt
Normal ticket               → Classification Prompt
```

Only long tickets incur the extra call. Rationale: reduce context, keep the classification prompt focused, improve handling of long narratives.

**Single measurement, not two.** The word count is computed exactly once, on the cleaned/normalized text (post Stage 2/3). That same measurement drives BOTH the Stage 1 `long_ticket` validation-report warning AND this routing decision. There must never be two independent word counts (e.g. one on raw text for the warning, another on cleaned text for routing) — that would let the warning and the actual routing behavior disagree near the boundary.

**Mandatory guardrail for the summarization prompt:** the summarizer must be instructed to **preserve every distinct issue and its key specifics**, not to produce a single-topic abstract. Summarization is the one place a secondary issue can silently disappear, which would defeat multi-issue detection (below). The summarization prompt explicitly states: *"Retain all distinct problems, requests, and complaints mentioned; do not merge or drop any issue."*

### Stage 5 — Classification

Tickets are classified with **one LLM call per ticket** at **temperature 0**, each ticket independent of every other. Each response passes through the bounded validate → coerce → single re-prompt → fallback sequence defined under *LLM Contract → Validation & Repair*. A configurable **concurrency cap** limits parallel in-flight calls to stay within provider rate limits.

**Continuous pool, no sub-batch boundary:** every ticket is submitted to a single worker pool up front, bounded only by the concurrency cap — not grouped into fixed-size batches with a drain-before-next-group barrier. A worker that finishes immediately picks up the next queued ticket, so no slot sits idle waiting on a straggler from an earlier group. (An earlier iteration grouped tickets into fixed-size batches that fully drained before the next group started; that added a synchronization point with no throughput benefit, since real parallelism was already governed by the concurrency cap alone — removed.)

**Ticket independence:** the failure, timeout, or malformed response of one ticket must not prevent classification of any other ticket. Each ticket succeeds or falls back on its own; there is no shared failure path.

**Real progress, off the same loop.** `classify_batch_streaming` is a generator form of this exact worker pool — it yields a progress event each time a ticket actually finishes (the same `as_completed` completion signal, not a separate timer or estimate), which `api/routes.py` forwards as an NDJSON line on `/analyze`'s response (see API Endpoints). `classify_batch` (non-streaming — used by the CLI and tests) just drains this generator and returns the final ordered list, so there is one core loop, not two.

### Stage 6 — Analytics

Pure Python. No LLM. Computes counts, distributions, theme frequency, urgency distribution, actionable counts, and KPIs.

### Stage 7 — Executive Summary

Python assembles the aggregate facts (distributions, top themes, top categories, notable counts). A **single LLM call** turns those numbers into a coherent, prioritized narrative. The model narrates pre-computed figures; it does not compute them.

**Summary grounding contract.** The summary generator:
- must **not invent statistics** — every number in the narrative must come from the Python-computed aggregate it was given;
- must **not contradict** the computed metrics;
- must **only reference Python-computed values**, never figures it derives or estimates itself.

This is what makes the summary trustworthy: the numbers are guaranteed correct because the model never produced them, only phrased them.

---

## Classification Taxonomy

The taxonomy and theme lists defined in this section are the **canonical enumerations** for the entire system. Prompt templates, Pydantic schemas, analytics, and frontend types must all derive from these values. No component may define its own category or theme strings independently — this is what prevents schema drift across the backend, model, and UI.

Nine fixed top-level categories. `Other` is the escape hatch — the model routes here rather than forcing a poor fit.

| Category | Scope |
|----------|-------|
| Billing & Payments | Charges, refunds, failed/duplicate payments, invoices, subscription/pricing |
| Account & Access | Login, passwords, OTP/2FA, lockouts, profile/permission settings |
| Performance & Reliability | Crashes, slowness, freezes, downtime, timeouts (app fails to run properly) |
| Functional Issues | App runs but behaves wrong — broken feature, incorrect data, sync/validation errors |
| Feature Requests & Enhancements | Requests for new capability or improvements to existing capability |
| Usability & User Experience | Works, but confusing, awkward, hard to navigate; also positive UX feedback |
| Support Experience | Feedback about the support process itself — response time, agent quality, resolution |
| Security | Unauthorized access, data privacy concerns, suspicious activity, vulnerability/phishing reports |
| Other | Uncategorized, unclear, or general feedback |

**Category design note (Performance vs Functional Issues):** Performance = the app fails to *run properly* (slow, crashing, down). Functional Issues = the app runs but does the *wrong thing* (a feature misbehaves, data is incorrect). This mirrors real triage boundaries and is the pair most prone to confusion; keep the definitions sharp in the prompt.

### Category-Owned Themes

Themes are **not global**, with one deliberate exception (`Positive Feedback`, below) — each category otherwise owns its own fixed theme list. The classification prompt must guarantee the selected theme belongs to the selected category (structurally enforced two-tier selection: pick category, then pick theme from that category's list only, or `Positive Feedback` from any category).

**Billing & Payments:** Failed Payment · Duplicate Charge · Refund Delay · Unexpected Charge · Subscription/Renewal Issue · Positive Feedback

**Account & Access:** Login Failure · Password Reset · OTP/2FA Problem · Account Locked · Profile Settings Issue · Positive Feedback

**Performance & Reliability:** App Crash · Slow Performance · Downtime/Outage · Timeout Error · High Resource Usage · Positive Feedback

**Functional Issues:** Function Not Working · Incorrect Data Displayed · UI Element Broken · Sync Issue · Validation Error · Positive Feedback

**Feature Requests & Enhancements:** New Feature Request · Enhancement Request · Integration Request · Workflow Improvement · Positive Feedback

**Usability & User Experience:** Confusing Navigation · Poor Layout · Hard to Find Feature · Accessibility Issue · Positive Feedback

**Support Experience:** Slow Response · Unhelpful Agent · Issue Unresolved · Difficult to Reach Support · Positive Feedback

**Security:** Unauthorized Access · Data Privacy Concern · Suspicious Activity · Vulnerability Report · Phishing/Scam Report · Positive Feedback

**Other:** General Feedback · Unclear · Requires Human Review · Positive Feedback

> Themes are a starting set and should be trimmed to match the dataset. A theme that no ticket ever maps to is dead weight and should be removed. `General Feedback` exists so non-complaint feedback that isn't specifically praise has a valid home under `Other`.

**`Positive Feedback` — cross-category exception.** Formerly `Positive Experience`, owned only by Usability & User Experience. It is now valid under every category (including `Security` and `Other`), replacing the old category-exclusive theme. This is the one deliberate break from "themes are category-owned" — the theme∈category validator must special-case it as universally valid. **Trade-off, accepted knowingly:** this theme partly duplicates the `sentiment` field (a ticket themed `Positive Feedback` will almost always carry `sentiment: Positive`) — kept anyway because it gives a stakeholder a direct theme-level filter for praise ("show me the positive feedback") without cross-referencing sentiment, which is a real dashboard-readability win worth the redundancy.

**Categorization rule for positive feedback.** Making the theme cross-category does NOT change how the *category* is chosen — positive feedback is categorized by its topic, exactly like any other ticket. Pick the category describing what the praise is about (praise about the UI/redesign → `Usability & User Experience`; praise about billing/payment → `Billing & Payments`; praise about a support interaction → `Support Experience`; etc.), then attach the `Positive Feedback` theme. `Other` is for praise with no identifiable topic at all (e.g. "great product, thanks!") — it is not a default dumping ground just because the theme happens to be cross-category.

**`Requires Human Review` — fallback theme, and now also a deliberate model choice.** Added under `Other`. This is the theme the system assigns whenever a ticket falls back (see Fallback Shape). It is also now explicitly instructed as a direct model choice — narrower than ordinary vagueness — for text that is readable but genuinely confusing or self-contradictory in a way a human would need to untangle: (a) the ticket asserts something and then cancels/reverses that same claim; (b) it confidently references specific context that was never given; (c) it jumps between unrelated topics with no connecting logic (not two real distinct issues — that's multi-issue, see below); (d) it states an urgent problem and then flatly denies it matters with no resolving explanation. This is a genuinely different trigger from `General Feedback` (vague but readable) or `Unclear` (no interpretable content) — ordinary vagueness must still route to those two, not here. A model-chosen vs. fallback-assigned occurrence remains indistinguishable by design — both are exactly the same signal (see Multi-Issue Handling / Fallback Shape / Analytics for the `fell_back_count` metric this drives), and this was true even before the explicit instruction existed; the instruction just makes the model-chosen path a real, defined, everyday occurrence instead of a theoretical one. `Unclear` is unaffected and remains available for a ticket the model successfully classifies but genuinely can't place — a valid, non-fallback classification, distinct from a review flag.

**Vagueness threshold, fixed after review feedback.** A vague ticket with no named feature/action (e.g. "Not sure this is working as I expected") was previously getting classified into a specific category with full confidence — overconfident, since nothing in the text names what's failing. The prompt now requires a named subject before picking a specific category; otherwise it routes to `Other` (`General Feedback` if there's some readable content, `Unclear` if there's essentially none, e.g. a single word). Fixed the intended case and also cleared a previously-open low-signal mismatch in the eval set. One known side effect: a single borderline ticket (Feature Request vs. Usability boundary) flipped again under this change — it had already flipped once before under an unrelated edit, so it appears to be an inherently fragile boundary case rather than something this specific change broke; not chased further.

---

## Sentiment, Urgency & Actionable

All three are discrete, closed enumerations — chosen for consistency (they survive the identical-input test) and actionability (no one acts on a decimal).

**Sentiment:** `Positive` · `Neutral` · `Negative`
- No `Mixed` value. A ticket with both praise and complaint is classified by its **dominant overall sentiment**.
- The discrete label remains the field every downstream decision is built on — it is what carries everything that gets acted upon.

**Sentiment score:** a continuous float in `[-1.0, +1.0]`, one-decimal precision, accompanies the discrete label as of this revision. Ticket-level only — never present on `additional_issues` (sentiment and sentiment score are both whole-ticket properties, not per-issue).
- **Sign must agree with the discrete label:** `Positive` → `(0, +1]`, `Neutral` → `[-0.5, +0.5]`, `Negative` → `[-1, 0)`.
- **Calm-but-unresolved convention (Neutral-labeled tickets only):** a `Neutral`-labeled ticket reporting a real unresolved problem but written in a calm, non-emotional tone should score mildly negative (approximately -0.2 to -0.3), not 0.0. The label stays `Neutral` — the situation isn't emotionally charged enough to call it `Negative` — but the score should reflect the mild negative lean rather than sitting at dead center, which would falsely read as "no issue at all." This convention is explicitly scoped to `Neutral` tickets — it is not a general "calm tone" discount.
- **Severity, not tone, drives magnitude on `Negative`-labeled tickets.** Found via review feedback: multiple genuinely different `Negative` tickets (a duplicate charge, a broken button, a blocked login) were all landing on the identical -0.3 score, regardless of how serious each situation actually was — the model was anchoring on the Neutral-band convention's example number rather than reasoning about real severity. Fixed by instructing the model to judge how bad the underlying situation is from content alone (as if reading it in an angry tone), independent of whether the actual wording is calm or emphatic. A calmly-worded but severe problem (days-long lockout, data loss) must score strongly negative; an angrily-worded but minor complaint stays mildly negative.
- **Severity reasoning must not leak into urgency.** The first fix attempt explicitly anchored score magnitude to urgency tiers ("High-urgency tickets typically score -0.6 to -1.0...") — this backfired: the model started reasoning backward from a desired score to a different urgency value than it would otherwise pick, measurably shifting urgency accuracy on unrelated tickets. Fixed by removing the urgency-tier anchor and adding an explicit instruction that severity judgment for scoring and the urgency decision must be reasoned independently. Residual note: at full-eval-set scale, urgency accuracy remains around 77-81% regardless of this fix — consistent with urgency being a persistently noisy field across many borderline tickets throughout this project, not something this specific change meaningfully moves either direction.
- **Enforced by Pydantic validation** — an out-of-band score (e.g. `sentiment: Negative` paired with `sentiment_score: 0.6`) fails validation and is repaired through the same validate → coerce → re-prompt → fallback sequence as any other invalid response, not treated as a special case.
- The score is a bounded companion for finer-grained dashboard readability (e.g. charting sentiment on a continuum), not an independent classification decision — the discrete label still drives everything the earlier "no continuous score" reasoning cared about (no decision hinges on the decimal).
- **All aggregates over the score** (e.g. an average sentiment score across a batch, or a weekly trend once persistence exists) **are computed in Python — never by the model.** Same rule as every other number (Core Principle 1); the model only ever emits one ticket's own score, never a computed aggregate.

**Urgency:** `High` · `Medium` · `Low` — defined by impact, independent of tone:
- `High` — blocks core functionality: severe outage, payment failure, or a security/access issue.
- `Medium` — an important issue that has a workaround or limited impact.
- `Low` — minor inconvenience, cosmetic issue, suggestion, or praise.

Urgency is impact-based, not tone-based: a calmly worded "I can't log in and have tried everything" is `High`; an angrily worded complaint about button color is `Low`. This keeps priority honest and consistent regardless of how the customer phrased it.

**Actionable:** `true` · `false` — whether the ticket requires follow-up or intervention by a product, engineering, support, or business team. Praise or purely informational feedback with no required action is `false`. This makes the field an objective "does someone need to do something" test rather than a subjective judgment.

---

## Multi-Issue Handling

A ticket may contain more than one issue. This is handled in the **single classification call** — never an additional LLM call. The model identifies all issues, selects one primary, and returns the rest as `additional_issues`.

- **Primary** carries full enrichment: category, theme, sentiment, sentiment_score, urgency, actionable.
- **Additional issues** carry category, theme, and **urgency**. (Urgency is included so a mild primary issue paired with an urgent secondary issue is not lost. Sentiment and sentiment_score are intentionally omitted from secondary issues — both are per-ticket properties, not per-issue.)
- **Analytics use the primary issue** for headline distributions. Additional issues are preserved for detailed inspection and urgency-aware views but are intentionally excluded from headline metrics to avoid double-counting tickets.

**Data model note:** the output is structured to allow multiple issues from day one. First release aggregates on the primary; promoting additional issues into headline analytics later is a scope expansion, not a schema rewrite. When that expansion happens, the denominator shifts from *tickets* to *issues* and the dashboard must state which it is counting.

**Known limitation — dense multi-issue tickets.** On a long ticket bundling several genuinely distinct problems (e.g. a login failure, incorrect data, a broken export, and unresponsive support all in one message), primary-issue selection is an inherent judgment call — reasonable readers, human or model, can disagree on which of several real problems is "the" primary one. Instruction 11's guidance (primary = the first-reported concrete problem on a clean two-issue ticket; weigh holistically only on 3+ distinct problems) narrows this but does not eliminate it.

**Known limitation — severity bias on two-issue tickets.** Measured directly: of 6 clean two-clause multi-issue tickets in the eval set, the model gets 4/6 right by correctly keeping the first-reported issue primary. On the other 2, the *second*-stated issue objectively reads as more technically severe than the first (e.g. "can't log in... and then the app crashes" — the crash outranks the login failure; "checkout failed... and support was unresponsive" — total support silence outranks a retriable payment failure), and the model overrides the first-reported issue in favor of the more severe-sounding one, despite an explicit instruction to keep sequence over severity. Two independent prompt-wording attempts to eliminate this (a softer "default to first" phrasing, then a "hard rule, no exception" phrasing) failed to fully fix it — the hard-rule version additionally broke a previously-correct case, indicating the model has a real trained bias toward severity-based primary selection that prompt wording alone does not fully override at temperature 0. Net effect is bounded and quantified, not open-ended: this affects tickets that (a) report exactly two problems, (b) in sequence, where (c) the second is markedly more severe-sounding than the first. It does not affect single-issue tickets, tickets where the more severe issue is reported first, or 3+ issue tickets (a different, already-documented limitation above). Accepted as a residual risk rather than chased further, since incremental prompt tightening was already shown to trade one failure for another.

---

## LLM Contract

### Input
- Cleaned, PII-redacted feedback (a summary, for long tickets).
- Instructions to select category, then a theme from that category, determine sentiment and urgency, identify additional issues, mark actionable, and return valid JSON only.

### Classification Prompt Requirements

The classification prompt must:
- Select exactly one primary category.
- Select exactly one theme from that category (or `Positive Feedback`, valid under any category).
- Determine dominant overall sentiment.
- Determine a ticket-level sentiment score, sign-consistent with the sentiment label.
- Determine urgency.
- Determine actionable status.
- Preserve additional issues.
- Never invent categories or themes.
- Return valid JSON only.

### Summarization Prompt Requirements

The summarization prompt must:
- Preserve every distinct issue, request, and complaint.
- Preserve important entities and chronology when relevant.
- Remove repetition, greetings, and filler.
- Never merge or omit separate issues.

### Prompt ownership
Prompt templates are implementation artifacts. This document defines their **required behavior** — the constraints above — not their exact wording. Prompt text may be refined or rewritten freely as long as it satisfies these requirements and produces the defined schema. Improving a prompt is not an architectural change.

### Output requirements
- Strict JSON, one object per ticket.
- No markdown, no prose outside the JSON.
- Category and theme drawn only from the fixed taxonomy; theme must belong to the chosen category.
- Schema-validated before analytics; repaired once; replaced with a valid fallback on failure.

### Output Schema

```json
{
  "ticket_id": "string",
  "feedback_text": "string",
  "was_summarized": false,
  "primary_category": "Account & Access",
  "primary_theme": "Login Failure",
  "sentiment": "Negative",
  "sentiment_score": -0.8,
  "urgency": "High",
  "actionable": true,
  "additional_issues": [
    {
      "category": "Performance & Reliability",
      "theme": "App Crash",
      "urgency": "Medium"
    }
  ],
  "warnings": []
}
```

`ticket_id`, `feedback_text`, `was_summarized`, and `warnings` are backend-attached, not model output — `feedback_text` is the already-cleaned, PII-redacted input text (not the raw upload), attached so the Feedback Explorer has real text to search/sort/filter on; `was_summarized` records whether this ticket was long enough to be routed through Stage 4 summarization before classification; `warnings` carries the row's Stage 1 validation flags (`html_present`/`markdown_present`/`duplicate_feedback`/`long_ticket`), attached after classification so a row-level quality signal reaches the dashboard without the model ever reasoning about it.

**The model's own output is a pure enumeration block, plus one bounded numeric field (`sentiment_score`).** No free-text/reasoning field is included. A prose rationale drives nothing in the first release (it does not condition classification and is not aggregated), costs output tokens on every call, and is the one field a model can waffle in — occasionally destabilizing the structured fields around it. Keeping the model's own output pure-enum-plus-bounded-numeric maximizes consistency, which is the primary correctness goal. `sentiment_score` doesn't reintroduce that risk — it's a single bounded float validated against the discrete label, not open prose. If evaluation later shows accuracy is weak specifically on ambiguous multi-issue tickets, the targeted fix is a reasoning-first field (rationale produced *before* the labels so it conditions them) — added only if the confusion data justifies it, and constrained to a short quoted trigger phrase rather than open prose.

### Validation & Repair

Every LLM response passes through a fixed, bounded recovery sequence. The contract is **repair at most once, never loop, always end in a valid object** — one bad ticket never crashes the batch.

1. **Validate.** Parse the response and validate it against the Pydantic schema. Enums are closed sets, so an invented category/theme or a wrong-cased value (`negative` instead of `Negative`) fails validation rather than silently poisoning the data. If it passes, done.

2. **Coerce (free, deterministic).** On failure, first attempt a cheap Python fix with no model call: strip markdown code fences (```` ```json ````), trim whitespace, extract the outermost JSON object, and re-parse. Formatting noise — the most common cause of a malformed response — is fixed here for zero cost and zero latency. Re-validate. If it now passes, done.

3. **Re-prompt (one LLM retry).** If coercion still fails, retry the model **exactly once** with the validation error appended as a nudge (e.g. *"Your previous output failed validation: {error}. Return ONLY valid JSON matching the schema."*). Validate the result.

4. **Fallback.** If the retry still fails, emit the fallback shape (below). Never a third attempt, never an exception to the caller.

**Why coercion before re-prompt.** At batch scale a re-prompt is a whole extra LLM call; a stray code fence does not warrant one. The free Python pass resolves the common case, so the paid retry is reserved for genuinely malformed output. This preserves the exact "repair once → fallback" reliability contract while cutting repair cost on large batches.

**Applies uniformly to every failure type — no shortcuts.** A response that fails to parse at all (broken JSON inside a tool/function call, or the model not calling the expected tool/function) is explicitly NOT a special case permitted to skip straight to fallback. It must go through the same coerce step and the same one guaranteed re-prompt as a schema-validation failure (invented/wrong-cased enum, theme/category mismatch, out-of-band `sentiment_score`) before fallback is allowed to fire. The bounded sequence — validate → coerce → one re-prompt → fallback — is the contract for every failure mode without exception; only after coerce AND the one re-prompt have both been tried does fallback happen.

**Transient API errors** (429 / 5xx / timeout) are handled separately from validation: retry with a short backoff. Auth errors are **not** retried. Every unrecovered error path — validation or API — ends in the fallback shape, never a crash. This is distinct from the one validation re-prompt above and does not count against it.

### Fallback Shape

On unrecoverable failure for a ticket, emit a valid object that never breaks analytics:

```json
{
  "ticket_id": "string",
  "feedback_text": "string",
  "was_summarized": false,
  "primary_category": "Other",
  "primary_theme": "Requires Human Review",
  "sentiment": "Neutral",
  "sentiment_score": 0.0,
  "urgency": "Low",
  "actionable": false,
  "additional_issues": []
}
```

The same graceful path handles out-of-scope inputs (non-English, spam/junk): they route to `Other / Requires Human Review` rather than raising an exception. Not handling a case well is acceptable in scope; crashing on it is not.

**Fallback = human review, one signal, counted once.** The fallback theme is `Requires Human Review`, not `Unclear` (see Category-Owned Themes). "Fell back" and "requires human review" are treated as the identical signal, not two separate things that could disagree — there is exactly one count for it (`fell_back_count`, see Analytics Specification), never a separate "review-flagged" tally alongside a separate "fell back" tally.

---

## Analytics Specification

Computed in Python over validated results:

- Total feedback processed
- Total skipped rows (with reasons)
- Category distribution (by primary category)
- Sentiment distribution
- Theme frequency (by primary theme)
- Urgency distribution (primary; optional urgency roll-up including `additional_issues`)
- `high_urgency_count` — count of `High`-urgency tickets, surfaced as its own field (matches the "High Urgency" KPI below, not just derivable from the urgency distribution)
- Actionable feedback count
- Top recurring themes
- Top categories
- `fell_back_count` — count of tickets that resolved to the fallback shape (== `Requires Human Review` count, per Fallback Shape). A quality signal for how much of the batch needs human attention, not an error metric.
- `theme_sentiment_avg` — mean `sentiment_score` per primary theme (theme → one-decimal average), computed in Python over the per-ticket scores the model already returned. This is the "which issues are customers most unhappy about" signal — a theme with a very negative average is a priority even if its raw frequency isn't the highest. Never computed by the model (Core Principle 1). **Deliberately excluded from the executive-summary prompt's payload** (`prompts/executive_summary.py`) — a raw -1.0-to-+1.0 number reads as a confusing bare score in prose (e.g. "scored a sentiment of 1.0") with no context a stakeholder can interpret; it's kept in the API response for other consumers (e.g. a future per-theme chart) but structurally cannot reach the narration call.
- Optionally, an average `sentiment_score` across processed tickets (single-batch; a time-windowed/weekly version requires persistence — see Deferred Extensions)

**Top category/theme tie contract.** `top_category`/`top_theme` are populated ONLY when there is a single, unambiguous leader. On a tie for the highest count, both are `null`, and `category_leaders`/`theme_leaders` list every tied entry instead. Any consumer, including the frontend, must handle the `null` case explicitly and render the leaders list rather than assuming a singular winner always exists.

---

## Dashboard KPI Definitions

| KPI | Definition |
|-----|-----------|
| Total Feedback | Count of valid processed rows |
| Skipped Rows | Invalid rows rejected during validation |
| Positive % | Positive / Total × 100 |
| Negative % | Negative / Total × 100 |
| Top Category | Highest-frequency primary category — `null` on a tie; see tie contract in Analytics Specification |
| Top Theme | Highest-frequency primary theme — `null` on a tie; see tie contract in Analytics Specification |
| High Urgency | Count of High-urgency tickets — field name `high_urgency_count` |
| Actionable | Count of tickets marked actionable |
| Needs Review | Count of tickets that fell back — field name `fell_back_count`; a quality signal, not an error count |
| Processing Success Rate | Processed rows / Total uploaded rows × 100 |

**Denominator rule:** all dashboard percentages use **processed (valid) tickets** as the denominator, unless the metric explicitly states otherwise. Processing Success Rate is the one deliberate exception — it divides by *total uploaded* rows, because its whole purpose is to measure how many uploads survived validation. Skipped rows never enter any other percentage.

---

## Dashboard Specification

| Widget | Source |
|--------|--------|
| Headline Summary (one-line strip) | Composed client-side from `analytics`/`validation_report` fields already in the response (tickets analyzed, top issue, % negative, high-urgency count, % actionable) — no new computation, just leads with the conclusion instead of burying it in a sidebar |
| KPI Cards | Analytics engine. Positive/Negative/Top Category/Top Theme/High Urgency/Actionable/Needs Review are click-to-filter, feeding the same filter state as the charts and Feedback Explorer |
| Category Distribution (chart) | Category counts |
| Sentiment Distribution (chart, donut) | Sentiment aggregation |
| Theme Frequency (chart) | Theme aggregation — capped to the top 8 by count; the sub-label states the true total ("top 8 of N") rather than silently truncating |
| Urgency Breakdown (chart, donut) | Urgency aggregation |
| Executive Summary (text) | Summary generator |
| Validation status (skipped / needs-review toggles) | `validation_report.skipped_rows` and items whose `primary_theme` is `Requires Human Review` — each rendered as a toggle chip that expands the real row list, not just an aggregate count |
| Feedback Explorer (table) | Structured feedback objects with search, sorting, filtering (category/theme/sentiment/urgency/actionable), and pagination (15 rows/page, resets to page 1 on any filter/search/sort change or a new upload — so a 100+ ticket batch never dumps one unbroken list) — search/filter operates on the `feedback_text` field now returned per item; `was_summarized` and row-level `warnings` are shown as badges. Also renders on a historical replay (see Multi-Week Persistence), using that upload's persisted `items` |
| Vs Last Week | Shown on the live dashboard (and preserved on replay of any upload that had one) when `comparison` is non-null. Each tile shows a before → after value plus a two-bar mini chart, colored by whether the metric's direction is actually good or bad news for that specific metric (e.g. a High Urgency count *dropping* is green, not red) — never a bare delta with no baseline. See Multi-Week Persistence for the full field list |
| History Sidebar | Collapsed by default, toggled open via a "History (N)" button that only appears once a dashboard (live or replayed) is on screen — never shown on the idle landing screen. Lists every past upload by filename + timestamp; clicking one replays that upload's own dashboard read-only; a delete icon per row requires an inline Yes/No confirm before calling `DELETE /uploads/{id}` |
| Chat with Tickets (widget) | A gradient orb, fixed bottom-right, rendered only once a dashboard (live or replayed) is on screen — same visibility rule as History. Breathes/gradient-shifts while idle, morphs into a chat panel on click. Scope toggle (This dashboard / All history); answers come from `POST /chat` (see Chat with Tickets (RAG) below), grounded in real computed facts and/or cited retrieved tickets, never invented |

Every chart must be self-explanatory: titled, axis-labeled, and interpretable by a stakeholder without a walkthrough. Bar charts additionally carry vertical gridlines for a scale reference and are keyboard-accessible (Tab + Enter/Space per bar), not mouse-only. The dashboard consumes processed API data only and issues no LLM calls.

---

## API Endpoints

The classification pipeline itself still runs in a **single request** — the CSV is uploaded and fully processed in one call, streamed back as it progresses. What changed from the original stateless design: that same call now also **persists** its result to Postgres on the way out (see Multi-Week Persistence, next section), and three small read/delete endpoints exist purely to browse and manage that history. There is still no `upload_id` you pass *in* — `/analyze` never takes one — but the response now hands you back the `upload_id` it was saved as, for the history endpoints to use.

| Endpoint | Purpose |
|----------|---------|
| `POST /analyze` | Upload a CSV, run the full pipeline, persist the result; returns the complete result payload |
| `GET /uploads` | List every past upload (id, timestamp, filename), newest first — powers the history sidebar |
| `GET /uploads/{id}` | Replay one past upload's full dashboard read-only (aggregate + items + its own comparison, if it had one) |
| `DELETE /uploads/{id}` | Permanently delete one upload and its ticket items (cascades) |
| `POST /chat` | RAG + facts chat over persisted tickets — see **Chat with Tickets (RAG)** below |

### `POST /analyze`

**Request:** multipart CSV file.

**Response:** streamed as newline-delimited JSON (NDJSON) — still one request, one response; it just isn't sent as a single blob. A progress line each time a ticket finishes classification (off the real worker-pool `as_completed` loop in `pipeline/classify.py`, not a fake timer), one "summarizing" line, then a final line with the complete payload:

```json
{"type": "progress", "stage": "classifying", "done": 42, "total": 97}
{"type": "progress", "stage": "summarizing", "done": 97, "total": 97}
{"type": "result", "data": {
  "validation_report": {
    "total_rows": 100,
    "processed": 97,
    "skipped": 3,
    "skip_reasons": {},
    "skipped_rows": [ /* {"ticket_id": "...", "reason": "empty_or_null_feedback"}, one per skipped row */ ],
    "fell_back_count": 2
  },
  "items": [ /* structured feedback objects, one per processed ticket — each carries a
                `warnings` list (html_present/markdown_present/duplicate_feedback/long_ticket)
                from row-level validation, attached after classification, never model output */ ],
  "analytics": { /* category, sentiment, theme, urgency distributions and KPIs */ },
  "summary": "Executive summary narrative — now also grounded in the week-over-week
               diff below, when one exists (see Multi-Week Persistence)",
  "upload_id": 42,
  "uploaded_at": "2026-07-28T12:16:55.545472+05:30",
  "comparison": { /* null on the very first upload ever — see Multi-Week Persistence
                     for the full shape */ }
}}
```

A consumer that doesn't care about progress can read the whole body and parse only the last line's `data`.

**CORS** is currently permissive (`*`) for local/demo use; lock down to specific origin(s) before production deployment.

---

## Multi-Week Persistence

Every `/analyze` call now persists its result to Postgres, turning Loom from a one-shot report generator into something that remembers and tracks itself over time: a history sidebar to reopen any past upload, and an automatic "vs last week" comparison on the current one. This section is the built contract — the plan that preceded it is superseded by what's described here.

**Why Postgres, not SQLite.** SQLite was the original placeholder choice (see the old Deferred Extensions entry, now folded into this section). Postgres was chosen instead because RAG is planned on top of this same feature and needs to store + embed per-ticket text regardless — Postgres via the `pgvector` extension (already installed alongside the app) can hold those embeddings in the same database and even the same `ticket_items` table, rather than standing up a second storage system for RAG later.

**Schema (`backend/storage/db.py`):**

```text
analysis_snapshots
├── id                 SERIAL PRIMARY KEY
├── uploaded_at        TIMESTAMPTZ, default now()
├── source_filename    TEXT — the uploaded CSV's original filename
├── validation_report  JSONB
├── analytics          JSONB
├── summary            TEXT
└── comparison         JSONB, nullable — null only for the very first upload ever

ticket_items
├── id                 SERIAL PRIMARY KEY
├── snapshot_id        INTEGER REFERENCES analysis_snapshots(id) ON DELETE CASCADE
├── ticket_id          TEXT
└── item               JSONB — the full per-ticket object (same shape as /analyze's `items[]`)
```

One `ticket_items` row per ticket per upload. `ON DELETE CASCADE` means deleting an upload deletes its tickets with it — no separate cleanup query. Schema is created/migrated via `ensure_schema()` at app startup (`CREATE TABLE IF NOT EXISTS` + `ADD COLUMN IF NOT EXISTS`), so an older running database picks up new columns/tables without a manual migration step.

**One-upload-equals-one-week.** Each CSV's tickets are assumed to already fall within roughly one week's range — the upload itself is the week, identified by its own `uploaded_at` timestamp. There is no per-row date-bucketing logic; that's a deferred idea for a hypothetical future live/continuous-feed scenario, not needed for how the tool is actually used today (one batch upload at a time).

**The week-over-week diff (`backend/storage/compare.py`).** On each new upload, *before* saving it, the backend reads whatever snapshot is currently the most recent one, and computes a diff between that snapshot's `analytics` and the new one's — pure Python over two already-computed aggregate dicts, no LLM involved. The diff carries both the delta AND the before/after absolute values for every metric — a bare `-36.7%` delta means nothing without knowing it moved from 70% to 33.3%, so both are always present:

```json
{
  "previous_uploaded_at": "2026-07-28T12:15:53+05:30",
  "sentiment_shift_pct": { "Positive": 56.7, "Negative": -36.7, "Neutral": -20.0 },
  "sentiment_pct_before": { "Positive": 10.0, "Negative": 70.0, "Neutral": 20.0 },
  "sentiment_pct_after":  { "Positive": 66.7, "Negative": 33.3, "Neutral": 0.0 },
  "category_shift_pct": { /* per-category percentage-point delta */ },
  "urgency_shift_count": { "High": -4, "Medium": -2, "Low": 5 },
  "urgency_count_before": { "High": 4, "Medium": 4, "Low": 2 },
  "urgency_count_after":  { "High": 0, "Medium": 2, "Low": 7 },
  "new_themes": [ /* themes present this upload, absent last upload */ ],
  "disappeared_themes": [ /* themes present last upload, absent this one */ ],
  "high_urgency_count_delta": -4, "high_urgency_count_before": 4, "high_urgency_count_after": 0,
  "actionable_pct_delta": -34.4, "actionable_pct_before": 90.0, "actionable_pct_after": 55.6,
  "fell_back_count_delta": 0, "fell_back_count_before": 0, "fell_back_count_after": 0
}
```

**"New/disappeared themes" is a plain set difference on `theme_frequency` keys — nothing more.** It means a theme had ≥1 ticket last upload and 0 this upload (or vice versa), not a verified fix or a confirmed new problem. At small batch sizes (10-100 tickets) this can just as easily be sampling variation as a real change. The frontend labels these "First seen this week" / "Not seen this week," deliberately avoiding "Resolved"/"New problem" language that would overclaim what the data actually shows.

**Direction-aware, not sign-aware, coloring.** A raw positive/negative check on a delta gets the color backwards for "lower is better" metrics — a High Urgency count *dropping* is good news and must render green, not red just because the number is negative. The frontend (`WeekComparison.tsx`) assigns each metric an explicit direction (`upIsGood` for Positive Sentiment/Actionable%/Low Urgency, `downIsGood` for Negative Sentiment/Medium+High Urgency, `neutral` for Neutral Sentiment) and colors by whether the change is good or bad for *that* metric, not by the sign of the number.

**The executive summary narrates the diff.** `compute_comparison`'s result is computed and attached to the response *before* the executive-summary LLM call, and passed into it (`prompts/executive_summary.py`'s `comparison_to_previous_week` field) — so the same one summary call that narrates this upload's own facts also states what changed since last time, with concrete before→after values ("negative sentiment fell from 70% to 33%"), grounded only in the numbers actually present in that object. Absent on the first-ever upload, and the prompt is explicitly told not to mention week-over-week change when it's absent.

**The diff is persisted, not recomputed on replay.** `comparison` is saved as part of the snapshot row at the time it's computed — so replaying an old upload via `GET /uploads/{id}` shows the diff exactly as it looked *then* (vs. whatever was "latest" at that time), not recomputed against today's latest upload, which would silently answer a different question.

**History sidebar UX.** Collapsed by default — a "History (N)" toggle button appears only once a dashboard (live or a replayed one) is actually on screen, never on the idle landing page. Clicking it expands a list of every past upload by filename + timestamp; clicking an entry replays that upload's own dashboard read-only (its own KPIs, charts, summary, comparison, and now its own Feedback Explorer table too, via persisted `ticket_items`). A trash icon per row requires an inline "Delete this upload? Yes/No" confirm before calling `DELETE /uploads/{id}` — deleting the entry currently being viewed falls back to the live view automatically.

**Known limitation, deliberately deferred.** Two concurrent `/analyze` requests (e.g. two browser tabs uploading at once) can both read the same "previous" snapshot before either has saved, so their comparisons are both computed against the same prior week rather than against each other. No ticket-level data is corrupted by this — it only affects which upload a comparison is computed against — and it's accepted as a non-issue for a local, single-user tool where concurrent uploads aren't a real usage pattern. Worth revisiting (e.g. `SELECT ... FOR UPDATE` around the read-latest + insert) only if multi-user concurrent use becomes real.

---

## Chat with Tickets (RAG)

A conversational widget on the dashboard ("Chat with Tickets" — the Morphing Orb, see Dashboard Specification) lets a user ask free-text questions about the tickets already analyzed. It is a fully separate request from `/analyze` — `POST /chat` — issued whenever the user asks a question, never as part of the upload flow.

**Two distinct data sources, never blended:**

1. **`current_upload_facts`** — the same Python-computed `analytics`/`comparison` the executive summary narrates from (see Stage 7). Real counts, percentages, top category/theme, and the week-over-week diff, for one specific upload. This is the *only* source aggregate/statistical/comparison questions ("what's the top category", "what changed since last week") are allowed to be answered from — retrieval is never treated as proof of a count or a total.
2. **`retrieved_tickets`** — a similarity-matched sample of individual ticket text (pgvector search, below). This is what content/specific-ticket questions ("who complained about X") are answered from, cited inline.

The model is explicitly instructed which source to use per question type, and never lets one source answer a question that belongs to the other — a single retrieved ticket is never presented as proof of "the top category" or "the main issue," and `current_upload_facts` alone can never produce a ticket quote.

### Embeddings — real `pgvector`, generated at ingest

Every `/analyze` call, after classification, sends each ticket's cleaned/redacted `feedback_text` to the embeddings API (`EMBEDDING_MODEL`, default `text-embedding-3-small` — one 1536-number float vector per ticket) in a single batch call, and stores the result in `ticket_items.embedding` — a genuine `pgvector` column (extension `CREATE EXTENSION IF NOT EXISTS vector`), not a JSON array. Left with **no fixed dimension** on the column itself, so a future change of `EMBEDDING_MODEL` (different vector length) doesn't require a schema migration.

**Best-effort, not a hard requirement.** If the embedding call fails, the upload still succeeds — the ticket is just stored with `embedding IS NULL` and silently excluded from chat retrieval, the same degrade-gracefully pattern as summarization (Stage 4). One bad embedding call never blocks an upload.

### Retrieval — a real pgvector query, no ANN index yet

`storage/snapshots.py`'s `search_similar_tickets()` embeds the user's question, then runs:

```sql
SELECT * FROM (
    SELECT t.ticket_id, t.item, s.id AS snapshot_id, s.source_filename, s.uploaded_at,
           1 - (t.embedding <=> %s) AS similarity
    FROM ticket_items t
    JOIN analysis_snapshots s ON s.id = t.snapshot_id
    WHERE t.embedding IS NOT NULL [AND t.snapshot_id = %s]
) ranked
WHERE similarity >= %s
ORDER BY similarity DESC
LIMIT %s
```

`<=>` is pgvector's cosine-distance operator (0 = identical direction, 2 = opposite); `similarity = 1 - distance` so higher reads as "more relevant." `scope="dashboard"` filters to one `snapshot_id`; `scope="all"` searches every upload. `RAG_MIN_SIMILARITY` (default `0.2`) drops anything below the bar entirely, rather than padding results out to `RAG_TOP_K` (default `5`) with unrelated tickets — a query can legitimately return fewer than `top_k`, or zero.

**No ANN index (ivfflat/hnsw).** An exact sequential scan is fast enough at the current scale (a handful of weekly snapshots, a few hundred tickets total) and simpler to reason about than an index. Add one only once history grows large enough for a full scan to matter — see Scope & Extensions.

**Known caveat: the similarity floor doesn't cleanly separate relevant from irrelevant.** OpenAI's `text-embedding-3-small` embeddings have a fairly high baseline cosine similarity between *any* two pieces of English text — a genuinely relevant ticket has been observed scoring *lower* (e.g. 0.15) than an unrelated one (e.g. 0.26) on the same query. `RAG_MIN_SIMILARITY` filters out the clearest noise (an off-topic query like "how to make a bomb" correctly returns zero results) but is not a precise relevance classifier for this embedding model — a genuinely relevant ticket can still be cut by the floor, and an irrelevant one can still clear it. Accepted as a known limitation, not something a threshold tweak alone fully fixes.

### What the model is told, and what it must refuse

`prompts/chat.py`'s `CHAT_SYSTEM_PROMPT` rules, in effect:

- Aggregate/statistical/"top/main/biggest/most common"/comparison questions ("top category", "what changed since last week", "which category performed better") → answer ONLY from `current_upload_facts`; if the specific figure isn't there (e.g. `comparison_to_previous_week` is absent — no earlier upload to compare against), refuse and point to the dashboard's KPI cards / "Vs Last Week" section, never guess from retrieved tickets.
- `top_category`/`top_theme` ties are respected the same way the dashboard does — null means named the tied leaders jointly, never present one as the sole winner.
- Content/specific-ticket questions → answer ONLY from `retrieved_tickets`, cite the ticket_id(s) inline.
- **A retrieved ticket may only be cited if its own fields actually match what's being asked** — e.g. a *Positive*-sentiment ticket must never be cited as an example of "worst reviews" just because it was the closest text match; if nothing in `retrieved_tickets` actually matches, say so plainly rather than citing a non-matching ticket anyway.
- A greeting or small talk gets a plain, brief reply — no forced citation, no discussion of either data source.
- Never infer "this week" vs. "last week" from a ticket's filename or position — the only real timing signal is each ticket's `uploaded_at`, and even that doesn't establish a full period's boundaries on its own.

**`scope="all"`'s "previous week" is always the single most recent upload's own comparison** — if a user asks a comparison question in `all` scope while actually meaning some older upload, the answer still reflects the latest upload's diff. A known ambiguity of the `all` scope, not a bug.

### Citation-based sources — not "whatever cleared the floor"

`sources` in the API response is not simply everything `search_similar_tickets` returned — it's only the tickets the model's answer actually cited, cross-checked from the answer text via regex (`\(ticket_id\)`, plus a fallback matching a bare letter-prefixed id like `D07`/`W03` anywhere in the text, since smaller models don't always follow the parenthetical format even when told to explicitly). This fixes two real observed failure modes: a greeting or a refusal dragging along unrelated retrieved tickets as if they backed the reply, and an answer that only needed one of several retrieved tickets showing all of them as if each were used.

### API contract

**`POST /chat`** — request:

```json
{ "question": "who is having trouble logging in?", "scope": "dashboard", "snapshot_id": 42 }
```

`scope` is `"dashboard"` (search one upload — `snapshot_id` required) or `"all"` (search every upload — `snapshot_id` ignored). Response:

```json
{
  "answer": "Ticket 1 reports being unable to log in with any password. (1)",
  "sources": [
    { "ticket_id": "1", "snapshot_id": 42, "source_filename": "week3.csv", "similarity": 0.49 }
  ]
}
```

No uploads saved yet, or nothing clears the similarity floor → a plain "nothing to answer from" message with `sources: []`, no LLM call wasted embedding a question that can't be answered (only the true "zero uploads exist" case skips the call entirely — once at least one upload exists, `current_upload_facts` usually gives the model *something* to reason from, so retrieval turning up nothing doesn't by itself short-circuit the call).

### UI — the Morphing Orb widget

A gradient orb (`frontend/src/components/ChatWidget.tsx`) sits fixed bottom-right, only rendered once a dashboard (live or historical replay) is on screen — same visibility rule as the History toggle, never on the idle landing page. It gently pulses/gradient-shifts while idle (pure CSS keyframes, `prefers-reduced-motion` respected) and **morphs shape** (circle → rounded panel, not a fade) when opened. A scope toggle ("This dashboard" / "All history") sits at the top of the panel; "This dashboard" is disabled when there's no current snapshot id to scope to. Messages render as chat bubbles with a typing indicator while a reply is in flight; cited tickets render as small chips under the assistant's reply (ticket id only — the similarity score is available on hover via the chip's `title`, not shown as visible text, since it's an internal ranking detail rather than something a user needs to read).

### Why Postgres was the right call here too

The multi-week persistence section already covered why Postgres (not SQLite) was chosen — RAG needing to store + embed per-ticket text regardless. This is that phase, now built: `pgvector` lives in the same `ticket_items` table as everything else, no second storage system stood up for it.

---

## Input Dataset Schema

| Column | Required | Description |
|--------|----------|-------------|
| feedback | Yes | Customer feedback text |
| id | No | Caller-supplied identifier, if the source system has one |
| source | No | Survey, App Store, Support, etc. |
| date | No | Feedback timestamp |

**Only `feedback` is required.** The uploaded CSV is expected to contain feedback text and nothing more; all other columns are optional. Extra columns are ignored unless used by analytics.

**Identifier handling.** The system assigns each processed ticket a `ticket_id` internally: it uses the caller-supplied `id` when present, otherwise it generates a stable one (row index or UUID). Callers never have to provide an identifier. The output `ticket_id` therefore always exists even though the input `id` column is optional — this is the mapping between the optional input `id` and the guaranteed output `ticket_id`.

---

## Logical Data Model

```text
Feedback
├── ticket_id
├── feedback_text                 (cleaned, PII-redacted text — backend-attached, not model output)
├── was_summarized                (bool)
├── primary_category
├── primary_theme
├── sentiment
├── sentiment_score                (float, [-1.0, +1.0], sign-agrees with sentiment)
├── urgency
├── actionable
├── additional_issues[]           (category, theme, urgency)
└── warnings[]                     (row-level flags from Stage 1 validation — html_present,
                                    markdown_present, duplicate_feedback, long_ticket; backend-
                                    attached post-classification, never model output)
```

This is the per-ticket shape held in memory during a request and returned in `items[]`. For how (and where) it's persisted across uploads, see **Multi-Week Persistence** — the same shape is stored verbatim as JSONB in `ticket_items.item`.

---

## Configuration

Runtime parameters via environment variables. No secrets in code.

| Variable | Purpose | Default |
|----------|---------|---------|
| LLM_MODEL | Model used for classification inference | — (required) |
| API_KEY | LLM provider key (env / secrets manager only) | — (required) |
| MAX_CONCURRENCY | Cap on parallel in-flight LLM calls | 5 |
| LONG_TICKET_WORD_LIMIT | Word count triggering summarization | 300 |
| MAX_UPLOAD_SIZE | Maximum CSV upload size | implementation-defined |
| REQUEST_TIMEOUT | Per-call timeout | implementation-defined |
| SUMMARY_MODEL | Optional model for executive summary generation | falls back to LLM_MODEL |
| LOG_LEVEL | Logging verbosity | INFO |
| DATABASE_URL | Postgres connection string for multi-week persistence | `postgresql:///loom_dev` (local Unix socket, current OS user) |
| EMBEDDING_MODEL | Model used to embed ticket text for RAG chat | `text-embedding-3-small` |
| RAG_TOP_K | Max tickets returned by one chat retrieval query | 5 |
| RAG_MIN_SIMILARITY | Minimum cosine similarity to keep a retrieved ticket at all | 0.2 |

---

## Error Handling & Reliability

- Skip invalid rows; report processed/skipped counts with reasons.
- Validate every LLM response against the schema; recover via the bounded validate → coerce → single re-prompt → fallback sequence (see *Validation & Repair*); never crash.
- Cap concurrency to respect provider rate limits.
- Log latency and failures per batch.
- **Idempotency:** re-running the same CSV through `/analyze` now creates a brand-new upload row rather than updating an existing one — by design, since "I uploaded this week's export again" and "this is a genuinely new week" are indistinguishable from the CSV content alone, and the tool doesn't ask the caller to assert which. There is no dedup-by-content check. This means an accidental double-upload of the same file shows up as two identical-looking history entries rather than being silently merged — acceptable for a manually-triggered local tool; revisit if this ever becomes an automated/scheduled upload pipeline where accidental re-runs are a real failure mode.
- No hardcoded secrets; keys in environment or a secrets manager.

---

## Error Codes

| Code | Meaning |
|------|---------|
| 4001 | Missing feedback column |
| 4002 | Empty CSV |
| 4003 | No valid feedback found |

`4004` (invalid LLM response, post-repair) and `5001` (AI provider unavailable) are removed from this table — they are unreachable under the "never crash the batch" invariant: every LLM/validation failure resolves to the fallback shape before it can ever reach the API boundary as an exception. The replacement signal is `fell_back_count` in the validation report (see Analytics Specification) — a quality metric describing how many tickets need human review, not an error code.

---

## Evaluation Strategy

Accuracy must be measured, not asserted. Built as `backend/eval.py`.

- **Golden set:** the demo dataset is hand-labeled (category, theme, sentiment, urgency, actionable) as it is built, so it doubles as a trusted answer key (`data/loom_answer_key_100.csv` / `loom_answer_key_10.csv`).
- **Hold-out discipline:** trivially satisfied by construction — the classification prompt (`prompts/classification.py`) uses zero few-shot examples at all, so there is nothing to exclude; every labeled ticket is genuinely held out.
- **Metric:** `eval.py` runs the real pipeline (validate → preprocess → classify, no mocked LLM) over a feedback CSV, joins results against the answer key by `id`, and reports overall + per-category + per-theme accuracy for category/theme, plus overall accuracy and a detailed per-ticket mismatch list for sentiment/urgency/actionable.
- **Answer-key "SKIP" rows** (rows expected to be rejected by `validate_csv` before classification) are checked separately — the script verifies they really were skipped, since a "SKIP" row that got classified anyway would itself be a bug, not scored for classification accuracy.
- **Known real numbers** (100-row set, GPT-4o-mini, 107 scorable tickets): category ~97%, theme ~94%, sentiment ~90%, actionable ~99-100%, urgency ~78-82% (the weakest field — see the sentiment-score section above for the investigated "Medium bias" and why prompt-tuning attempts to fix it were reverted after measuring no improvement). Includes a `human_review` case type (3 tickets) added to exercise the `Requires Human Review` vagueness-boundary trigger (see Category-Owned Themes) — scored 100% in the run that added it.
- **Confusion matrix:** deferred. Add it if a single accuracy number proves insufficient for locating error clusters (e.g. Performance vs Functional Issues confusion). It is an inexpensive follow-up, not a first-release requirement.
- **Data honesty:** if tickets are LLM-generated, hand-write or heavily edit a portion so the evaluation is not merely the model recognizing its own style.
- **LLM non-determinism caveat:** even at `temperature=0`, provider API calls are not perfectly bit-identical run-to-run in practice — category/theme accuracy has been observed to shift slightly between runs even when only unrelated prompt text changed. A single before/after `eval.py` run is not a fully reliable A/B signal for a small prompt tweak; multi-run averaging would be the fix if this becomes a blocker (not built).
- **`eval.py` measures classification accuracy only.** Chat with Tickets (RAG) is verified separately — via unit tests against a `FakeLLMClient` and manual live checks against a real backend — not by a golden-set accuracy script; it has no single "correct answer" per question the way a ticket's category/theme does.

---

## Dataset Specification

Approximately **100 tickets**, deliberately varied so the pipeline's behavior is demonstrable. Include:

- Normal single-issue tickets
- Multi-issue tickets
- Long tickets (> 300 words) to exercise summarization routing
- Duplicate tickets (for later optimization discussion)
- HTML / Markdown-formatted feedback (to exercise normalization)
- Invalid / empty rows (to exercise validation)
- A realistic mix of Positive, Neutral, and Negative — including genuine praise, not only complaints
- Coverage across all categories so none is permanently empty
- A few genuinely confusing/self-contradictory tickets (`human_review` case type) to exercise the `Requires Human Review` vagueness-boundary trigger — distinct from ordinary vague tickets (`low_signal`), which must keep routing to `General Feedback`/`Unclear` instead

The dataset is both the demo input and the evaluation bench. Each edge case the system claims to handle should have representative rows.

---

## Scope & Extensions

### In scope (first release)
- CSV upload → validation → normalization → PII redaction → classification → analytics → summary → dashboard
- Fixed taxonomy, category-owned themes, discrete sentiment/urgency
- Single-call multi-issue with `primary` + `additional_issues` (urgency-bearing)
- Long-ticket summarization routing with issue-preserving summaries
- Golden-set accuracy evaluation
- Single-period (current batch) analysis

### In scope (built after first release)
- **Multi-week persistence** — Postgres storage of every upload's aggregate snapshot + per-ticket items, an automatic week-over-week comparison narrated into the executive summary, and a history sidebar for read-only replay of any past upload. Full contract in **Multi-Week Persistence** above. Superseded the SQLite placeholder this used to name below.
- **Chat with Tickets (RAG)** — a conversational widget answering free-text questions over persisted tickets, backed by real `pgvector` similarity search plus the same Python-computed facts the executive summary narrates from. Full contract in **Chat with Tickets (RAG)** above. Supersedes the "RAG over feedback history" deferred entry this used to name below.

### Deferred — documented, not built
Each is a clean extension that does not require reworking the AI pipeline.

| Deferred capability | Why deferred / trigger to build |
|---------------------|--------------------------------|
| Duplicate-result caching | Consistency already achieved via temp 0 + discrete + closed lists. Build if repeated re-processing of identical CSVs becomes costly. |
| ANN vector index (ivfflat/hnsw) for chat retrieval | Chat with Tickets (built) does an exact `pgvector` `<=>` scan, no index. Fine at current scale (a handful of weekly snapshots); add an index once history grows large enough for a full scan to matter. |
| Hybrid keyword + vector search for chat | Pure semantic search can miss exact terms (ticket ids, error codes, names) that embeddings blur past. Add a keyword-match pass alongside the vector search once that starts mattering. |
| Recency-windowed default scope for chat's "all history" | At many more weeks of history, "all history" searching every upload gets noisier and costlier than it needs to be — a user asking about "lately" rarely means week 1 from months ago. Default to a recent window (e.g. last N weeks) unless the question implies otherwise. |
| Non-English support | Currently routed to `Other` gracefully. Build language detection + translation step when the dataset warrants it. |
| Spam / junk filtering | Currently routed to `Other` gracefully. Add a pre-classification gate to protect analytics when real streams introduce noise. |
| Emergent-theme detection | Fixed themes are blind to new issues, which pool in `Other`. Monitor the `Other` rate as the signal; the automated version is embedding-based clustering. |
| Chunking for extremely large tickets | Beyond the summarization threshold; build if inputs regularly exceed summarization limits. |
| Aspect-based sentiment | Correct answer for mixed-sentiment tickets (sentiment per issue). Scoped out; dominant sentiment used instead. |
| Human review workflow | For low-confidence classifications; build when a confidence signal is added. |
| API rate limiting | `/analyze` has no request-level throttling — a single caller can currently trigger unbounded concurrent batches, each making real LLM calls. `MAX_CONCURRENCY` bounds in-flight calls *within* one request, but nothing bounds *how many requests* can run at once. Fine for local/demo use with no public exposure; add per-client rate limiting (e.g. `slowapi`, or a gateway-level limit) before any public or multi-tenant deployment, to protect both cost and provider quota. |
| Concurrent-upload comparison race | Two simultaneous `/analyze` calls can both read the same "previous" snapshot before either saves (see Multi-Week Persistence's Known Limitation). Fix with `SELECT ... FOR UPDATE` if concurrent multi-user uploads become a real usage pattern. |
| Data retention policy for stored feedback text | `ticket_items.item` now persists redacted feedback text at rest (previously it only ever existed in-memory for one request). Redaction is a regex heuristic, not perfect (documented false-positive/leak caveats above) — worth a retention/deletion policy decision before this holds real customer data at any scale beyond local dev. |

---

## Project Structure

```text
backend/
├── api/                 HTTP endpoints and orchestration (routes.py, response_models.py)
├── pipeline/
│   ├── validate.py      file + row validation (4001/4002/4003, skip/warn rules)
│   ├── preprocess.py    normalization + PII redaction
│   ├── classify.py      batch classification, validation, repair, fallback
│   └── summarize.py     long-ticket routing + executive summary
├── analytics/           deterministic KPI/aggregation — no LLM import, ever
├── storage/             Postgres persistence (see Multi-Week Persistence + Chat with Tickets)
│   ├── db.py            connection + schema (analysis_snapshots, ticket_items + pgvector
│   │                    extension/column), registers the pgvector psycopg adapter
│   ├── snapshots.py      save/list/get/delete a snapshot + its ticket items,
│   │                    get_snapshot_facts() (analytics+comparison for chat),
│   │                    search_similar_tickets() (pgvector `<=>` retrieval)
│   └── compare.py       pure-Python week-over-week diff (before/after + delta)
├── prompts/             prompt templates and output contracts (incl. chat.py — RAG + facts)
├── schemas/             Pydantic models + canonical taxonomy (taxonomy.py)
├── services/            LLM client wrapper (chat completions + embeddings), typed errors
├── utils/               config loading
├── data/                sample/dev CSVs (git-ignored, not shipped)
├── tests/               pytest — one file per pipeline stage + an API-level suite
├── eval.py              classification accuracy vs. a hand-labeled answer key
├── cli.py               run the pipeline over any CSV from the terminal
└── main.py              FastAPI app, CORS, request timing, schema init on startup

frontend/
├── src/
│   ├── api/             analyzeClient.ts (the one POST /analyze call),
│   │                    uploadsClient.ts (GET /uploads, GET/DELETE /uploads/{id}),
│   │                    chatClient.ts (POST /chat)
│   ├── hooks/           useAnalyze() — request status + payload state;
│   │                    useUploadHistory() — history list + replay + delete;
│   │                    useChat() — chat widget open state, scope, messages, in-flight ask()
│   ├── types/           taxonomy.ts + analyze.ts + chat.ts, mirroring the backend contract
│   ├── components/      Nav, AmbientStatus, IdleLanding, HeadlineSummary, KpiCards,
│   │                    ValidationBanner, SummaryPanel, FeedbackExplorer, ExportButton,
│   │                    HistorySidebar, WeekComparison, ChatWidget (the Morphing Orb
│   │                    "Chat with Tickets" widget), charts/
│   │                    (DistributionBarChart, DonutChart, CategoryDistributionChart,
│   │                    ThemeFrequencyChart, SentimentDistributionChart, UrgencyBreakdownChart)
│   ├── pages/           DashboardPage — the single dashboard view (live + history-replay states)
│   ├── utils/           colors.ts (the one category/sentiment/urgency color map, also
│   │                    theme→category derivation), motion.ts (imperative tilt/glow —
│   │                    never setState, so hover never detaches a mid-click SVG node),
│   │                    exportReport.ts
│   └── test/            vitest setup + fixtures captured from the live backend
```

| Module | Responsibility |
|--------|----------------|
| api | Endpoints and request orchestration |
| pipeline | Validation, preprocessing, PII redaction, batching, LLM execution |
| analytics | Deterministic aggregation and KPIs |
| storage | Postgres persistence — snapshots, ticket items (+ embeddings), week-over-week diff, chat retrieval |
| prompts | Prompt templates and output contracts, incl. the RAG + facts chat prompt |
| schemas | Pydantic models and validation |
| services | External integrations — LLM client wrapper (chat completions + embeddings) |
| utils | Shared helpers |
| tests | Backend pytest suite (80 tests) — validation, preprocessing (incl. PII redaction edge cases), schema validators, analytics, the classification repair sequence, LLM client retry/backoff/auth behavior (incl. the embeddings call), executive-summary fallback paths, row-level `warnings` reaching the item, real per-ticket progress events streaming before the result, the multi-week persistence endpoints (comparison, history replay, delete + cascade), the `/chat` endpoint (both scopes, the similarity floor, citation-based sources filtering, facts inclusion), and the API endpoint, all without a real LLM call |

For the exact, currently-accurate directory listing and what each file does, see `backend/README.md` and `frontend/README.md` — this section is the high-level shape; the two READMEs are the maintained source of truth for file-level detail.

---

## Implementation Phases

1. Scaffold — FastAPI, React, folder structure, config.
2. Ingestion — CSV upload, validation, normalization, PII redaction.
3. Classification — prompt, schema, batching, validation/repair/fallback, long-ticket routing.
4. Analytics — deterministic aggregation and dashboard APIs.
5. Summary — number-facts assembly + narration call.
6. Frontend — dashboard, charts, feedback explorer, filters.
7. Evaluation & polish — golden-set accuracy, edge-case verification, error handling.

---

## Development Checklist

- [ ] Project scaffold and configuration
- [ ] CSV upload endpoint
- [ ] Validation layer (file + row)
- [ ] Normalization + PII redaction
- [ ] Long-ticket routing (issue-preserving summarization)
- [ ] Concurrency-bounded classification pool
- [ ] Classification prompt (two-tier category→theme, multi-issue)
- [ ] Output schema, validation, single repair, fallback shape
- [ ] Analytics engine
- [ ] Executive summary generation
- [ ] Dashboard APIs
- [ ] Frontend charts and feedback explorer
- [ ] Idempotent re-run handling
- [ ] Golden-set accuracy evaluation
- [ ] Edge-case verification against dataset

---

## Example

**Input tickets:**

| id | feedback |
|----|----------|
| 1 | Payment failed after checkout. |
| 2 | The app crashes every time I open Settings. |
| 3 | I love the new dashboard design! |

**Example classification output:**

```json
{
  "ticket_id": "2",
  "feedback_text": "The app crashes every time I open Settings.",
  "was_summarized": false,
  "primary_category": "Performance & Reliability",
  "primary_theme": "App Crash",
  "sentiment": "Negative",
  "sentiment_score": -0.7,
  "urgency": "High",
  "actionable": true,
  "additional_issues": []
}
```

**Example dashboard snapshot:**

```text
Total Feedback : 100
Processed      : 97
Skipped        : 3

Top Category   : Billing & Payments
Top Theme      : Failed Payment
Positive       : 28%
Neutral        : 17%
Negative       : 55%
High Urgency   : 14
Needs Review   : 2
```

**Example executive summary (narrated from pre-computed numbers):**

> Most feedback concerns payment reliability and application stability. Billing & Payments is the largest category and the dominant source of negative sentiment, driven primarily by failed payments — checkout reliability is the clearest priority. Performance & Reliability is the second most frequent category, concentrated in app crashes. Feedback on the redesigned dashboard is predominantly positive.
