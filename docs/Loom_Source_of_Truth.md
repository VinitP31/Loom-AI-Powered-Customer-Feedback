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
| AI | LLM API | Semantic classification and narration only |

---

## High-Level Architecture

```text
                         +----------------------+
                         |   React Dashboard    |
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
                                                         |
                                                 Dashboard Response
```

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
Batch Builder         group items; respect concurrency cap
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

**Honest note on the `[ID]` heuristic:** it is a digit-length heuristic (5–6 digit runs), not true ID-pattern matching (no prefix/format awareness). It can false-positive on incidental 5–6 digit numbers that aren't identifiers at all (an amount, a date-like number). Accepted as a reasonable approximation, not a precise pattern matcher.

### Stage 4 — Long-Ticket Routing

If a ticket exceeds **300 words**, it is first passed through a **summarization prompt**, and the summary is then classified. Otherwise it is classified directly.

```text
Long ticket ( >300 words )  → Summarization Prompt → Classification Prompt
Normal ticket               → Classification Prompt
```

Only long tickets incur the extra call. Rationale: reduce context, keep the classification prompt focused, improve handling of long narratives.

**Single measurement, not two.** The word count is computed exactly once, on the cleaned/normalized text (post Stage 2/3). That same measurement drives BOTH the Stage 1 `long_ticket` validation-report warning AND this routing decision. There must never be two independent word counts (e.g. one on raw text for the warning, another on cleaned text for routing) — that would let the warning and the actual routing behavior disagree near the boundary.

**Mandatory guardrail for the summarization prompt:** the summarizer must be instructed to **preserve every distinct issue and its key specifics**, not to produce a single-topic abstract. Summarization is the one place a secondary issue can silently disappear, which would defeat multi-issue detection (below). The summarization prompt explicitly states: *"Retain all distinct problems, requests, and complaints mentioned; do not merge or drop any issue."*

### Stage 5 — Batch Building & Classification

Tickets are grouped into batches for throughput management and classified with **one LLM call per ticket** at **temperature 0**. Batching improves execution efficiency only; each ticket is still classified independently. Each response passes through the bounded validate → coerce → single re-prompt → fallback sequence defined under *LLM Contract → Validation & Repair*. A configurable **concurrency cap** limits parallel in-flight calls to stay within provider rate limits.

**Batches are synchronous barriers:** the current implementation fully drains one batch (waits for every ticket in it to resolve) before submitting the next, even when concurrency slots are free. A continuous pool — bounded only by the concurrency cap, not batch boundaries, so batch N+1 can start filling free slots while batch N is still finishing — is a possible future optimization, not the current behavior.

**Batch independence:** the failure, timeout, or malformed response of one ticket must not prevent classification of any other ticket in the same batch. Each ticket succeeds or falls back on its own; there is no shared failure path across a batch.

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

**`Requires Human Review` — fallback theme.** Added under `Other`. This is the theme the system assigns whenever a ticket falls back (see Fallback Shape) — it replaces `Unclear` as the fallback target. It remains a normal, selectable theme like any other under `Other` (a model could in principle choose it directly for a confusing ticket), and a model-chosen vs. fallback-assigned occurrence is indistinguishable by design — both are exactly the same signal (see Multi-Issue Handling / Fallback Shape / Analytics for the `fell_back_count` metric this drives). `Unclear` is unaffected and remains available for a ticket the model successfully classifies but genuinely can't place — a valid, non-fallback classification, distinct from a review flag.

---

## Sentiment, Urgency & Actionable

All three are discrete, closed enumerations — chosen for consistency (they survive the identical-input test) and actionability (no one acts on a decimal).

**Sentiment:** `Positive` · `Neutral` · `Negative`
- No `Mixed` value. A ticket with both praise and complaint is classified by its **dominant overall sentiment**.
- The discrete label remains the field every downstream decision is built on — it is what carries everything that gets acted upon.

**Sentiment score:** a continuous float in `[-1.0, +1.0]`, one-decimal precision, accompanies the discrete label as of this revision. Ticket-level only — never present on `additional_issues` (sentiment and sentiment score are both whole-ticket properties, not per-issue).
- **Sign must agree with the discrete label:** `Positive` → `(0, +1]`, `Neutral` → `[-0.5, +0.5]`, `Negative` → `[-1, 0)`.
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
  ]
}
```

`ticket_id`, `feedback_text`, and `was_summarized` are backend-attached, not model output — `feedback_text` is the already-cleaned, PII-redacted input text (not the raw upload), attached so the Feedback Explorer has real text to search/sort/filter on; `was_summarized` records whether this ticket was long enough to be routed through Stage 4 summarization before classification.

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
| KPI Cards | Analytics engine |
| Category Distribution (chart) | Category counts |
| Sentiment Distribution (chart) | Sentiment aggregation |
| Theme Frequency (chart) | Theme aggregation |
| Urgency Breakdown (chart) | Urgency aggregation |
| Executive Summary (text) | Summary generator |
| Feedback Explorer (table) | Structured feedback objects with search, sorting, and filtering — search/filter operates on the `feedback_text` field now returned per item; `was_summarized` can be shown as a badge |

Every chart must be self-explanatory: titled, axis-labeled, and interpretable by a stakeholder without a walkthrough. The dashboard consumes processed API data only and issues no LLM calls.

---

## API Endpoints

The system is **stateless** with no database, so the entire pipeline runs in a **single request**. The CSV is uploaded and fully processed in one call that returns everything the dashboard needs. The frontend holds the response in memory and renders from it; the dashboard issues no further calls.

| Endpoint | Purpose |
|----------|---------|
| `POST /analyze` | Upload a CSV and run the full pipeline; returns the complete result payload |

### `POST /analyze`

**Request:** multipart CSV file.

**Response:**
```json
{
  "validation_report": { "total_rows": 100, "processed": 97, "skipped": 3, "skip_reasons": {}, "fell_back_count": 2 },
  "items": [ /* structured feedback objects, one per processed ticket */ ],
  "analytics": { /* category, sentiment, theme, urgency distributions and KPIs */ },
  "summary": "Executive summary narrative..."
}
```

**CORS** is currently permissive (`*`) for local/demo use; lock down to specific origin(s) before production deployment.

**Why a single call, not upload → analyze → dashboard.** With no database, a two-step flow would require holding uploaded data in server-side memory between requests, keyed by an `upload_id`. That temporary state is fragile (lost on restart, absent on a second worker) and is session management the MVP does not need. A single stateless call matches the no-DB design honestly. The multi-request shape (`POST /upload` → `upload_id` → `POST /analyze` → `GET /dashboard`, `GET /summary`) becomes the natural design **once persistence is added** — it is listed with that deferred extension, not built now.

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
└── additional_issues[]           (category, theme, urgency)
```

---

## Configuration

Runtime parameters via environment variables. No secrets in code.

| Variable | Purpose | Default |
|----------|---------|---------|
| LLM_MODEL | Model used for classification inference | — (required) |
| API_KEY | LLM provider key (env / secrets manager only) | — (required) |
| BATCH_SIZE | Tickets per batch | 10 |
| MAX_CONCURRENCY | Cap on parallel in-flight LLM calls | 5 |
| LONG_TICKET_WORD_LIMIT | Word count triggering summarization | 300 |
| MAX_UPLOAD_SIZE | Maximum CSV upload size | implementation-defined |
| REQUEST_TIMEOUT | Per-call timeout | implementation-defined |
| SUMMARY_MODEL | Optional model for executive summary generation | falls back to LLM_MODEL |
| LOG_LEVEL | Logging verbosity | INFO |

---

## Error Handling & Reliability

- Skip invalid rows; report processed/skipped counts with reasons.
- Validate every LLM response against the schema; recover via the bounded validate → coerce → single re-prompt → fallback sequence (see *Validation & Repair*); never crash.
- Cap concurrency to respect provider rate limits.
- Log latency and failures per batch.
- **Idempotency:** trivially satisfied by construction in the current design. Each `/analyze` call is stateless and independent — there is no persisted state anywhere for a re-run to double-count against, so "re-running the same upload must not double-count" is automatically true (there's nothing to double-count into). This becomes a real, non-trivial requirement (keying processing by upload/run identity so re-runs against stored results are safe) only once persistence is added — see the "Multi-period trends & persistence" row in Deferred Extensions, which is exactly where this requirement re-activates.
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

Accuracy must be measured, not asserted.

- **Golden set:** the demo dataset is hand-labeled (category, theme, sentiment) as it is built, so it doubles as a trusted answer key.
- **Hold-out discipline:** the tickets used as few-shot examples in the prompt are **excluded** from the tickets used to measure accuracy. Measuring against examples the model was shown inflates the result.
- **Metric:** run the held-out set through the pipeline and report accuracy (correct / total), overall accuracy, per-category accuracy, and per-theme accuracy.
- **Confusion matrix:** deferred. Add it if a single accuracy number proves insufficient for locating error clusters (e.g. Performance vs Functional Issues confusion). It is an inexpensive follow-up, not a first-release requirement.
- **Data honesty:** if tickets are LLM-generated, hand-write or heavily edit a portion so the evaluation is not merely the model recognizing its own style.

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

### Deferred — documented, not built
Each is a clean extension that does not require reworking the AI pipeline.

| Deferred capability | Why deferred / trigger to build |
|---------------------|--------------------------------|
| Duplicate-result caching | Consistency already achieved via temp 0 + discrete + closed lists. Arrives naturally with persistence (storage acts as cache). Build if repeated re-processing becomes costly. |
| Multi-period trends & persistence | Requires storage (SQLite is sufficient). The fixed taxonomy is already a stable-id vocabulary, so week-over-week deltas and new-theme detection drop in without touching the pipeline. The multi-request API shape (`POST /upload` → `upload_id` → `POST /analyze` → `GET /dashboard`/`GET /summary`) is adopted here, replacing the stateless single call, since results now persist and can be re-queried. **This is also where idempotency (Error Handling & Reliability) becomes a real, non-trivial requirement** — re-runs against persisted results must be keyed by upload/run identity to avoid double-counting, unlike today's trivially-idempotent stateless call. A time-windowed average `sentiment_score` (e.g. weekly) also arrives here, once there's a time axis to average over. |
| Non-English support | Currently routed to `Other` gracefully. Build language detection + translation step when the dataset warrants it. |
| Spam / junk filtering | Currently routed to `Other` gracefully. Add a pre-classification gate to protect analytics when real streams introduce noise. |
| Emergent-theme detection | Fixed themes are blind to new issues, which pool in `Other`. Monitor the `Other` rate as the signal; the automated version is embedding-based clustering. |
| Chunking for extremely large tickets | Beyond the summarization threshold; build if inputs regularly exceed summarization limits. |
| Aspect-based sentiment | Correct answer for mixed-sentiment tickets (sentiment per issue). Scoped out; dominant sentiment used instead. |
| Human review workflow | For low-confidence classifications; build when a confidence signal is added. |

---

## Project Structure

```text
backend/
├── api/                 HTTP endpoints and orchestration
├── pipeline/
│   ├── validate.py
│   ├── preprocess.py    normalization + PII redaction
│   ├── classify.py      batch classification, validation, repair, fallback
│   ├── summarize.py     long-ticket + executive summary prompts
├── analytics/           deterministic KPI/aggregation
├── prompts/             prompt templates and output contracts
├── schemas/             Pydantic models
├── services/            LLM client, file handling
├── utils/               shared helpers
└── main.py

frontend/
├── components/
├── pages/
├── hooks/
├── api/
├── types/
├── utils/
└── assets/
```

| Module | Responsibility |
|--------|----------------|
| api | Endpoints and request orchestration |
| pipeline | Validation, preprocessing, PII redaction, batching, LLM execution |
| analytics | Deterministic aggregation and KPIs |
| prompts | Prompt templates and output contracts |
| schemas | Pydantic models and validation |
| services | External integrations (LLM, files) |
| utils | Shared helpers |

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
- [ ] Batch builder with concurrency cap
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
