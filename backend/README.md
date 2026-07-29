# Loom Backend

AI-powered customer feedback classification. Upload a CSV of raw customer feedback, get back per-ticket classification (category, theme, sentiment, urgency, actionable), deterministic analytics, and a grounded executive summary — all in one request.

Full design rationale: [`docs/Loom_Source_of_Truth.md`](../docs/Loom_Source_of_Truth.md).

---

## Requirements

- Python 3.11+ (tested on 3.12)
- An OpenAI API key (classification + chat run on `gpt-4o-mini` by default, embeddings on `text-embedding-3-small` — see Configuration)
- Postgres 14+ running locally (multi-week persistence — history sidebar, week-over-week comparison, chat retrieval). `brew install postgresql@16 && brew services start postgresql@16` on macOS; `createdb loom_dev` once, and `createdb loom_test` if you'll run the test suite.
- **`pgvector` extension, matching your Postgres's major version.** Required — `ticket_items.embedding` is a real `pgvector` column, used by the "Chat with Tickets" feature. `brew install pgvector` only builds against whichever Postgres major version(s) Homebrew currently ships bottles for — if that doesn't match your running Postgres (e.g. brew's `pgvector` targets 17/18 but you're running `postgresql@16`), it silently won't load, and `CREATE EXTENSION vector` fails at startup. In that case build it from source against your actual server:
  ```bash
  git clone --depth 1 https://github.com/pgvector/pgvector.git
  cd pgvector
  PG_CONFIG=$(brew --prefix postgresql@16)/bin/pg_config make
  PG_CONFIG=$(brew --prefix postgresql@16)/bin/pg_config make install
  ```
  (swap `postgresql@16` for whatever version you're actually running). No Postgres upgrade needed, no data migration — this only adds the extension. `ensure_schema()` (`storage/db.py`) runs `CREATE EXTENSION IF NOT EXISTS vector` itself at startup once the extension is actually installed for your server.

---

## Setup (cold start)

Run these from the `backend/` directory.

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up Postgres + pgvector (required — see Requirements above for the
#    pgvector-build-from-source fallback if this fails)
brew install postgresql@16 pgvector
brew services start postgresql@16
createdb loom_dev
createdb loom_test          # only needed if you'll run the test suite

# 4. Configure environment
cp .env.example .env
```

Now open `.env` and fill in at minimum:

```
LLM_MODEL=gpt-4o-mini
API_KEY=sk-...your-real-key...
```

Everything else in `.env` has a working default (see Configuration below) — you only need to set `LLM_MODEL` and `API_KEY` to get started. `DATABASE_URL` defaults to `postgresql:///loom_dev` (connects via the local Unix socket as your current OS user) — only override it if your Postgres setup needs a different connection string. **Do not commit `.env`** — it's git-ignored on purpose.

If you skip step 4, both the CLI and the API will fail immediately at startup with `KeyError: 'LLM_MODEL'` — that error means `.env` is missing or empty, not a bug. If you skip step 3 (or `brew install pgvector` doesn't match your Postgres's major version), the API fails at startup instead — either connecting to Postgres at all, or on `CREATE EXTENSION vector` — see Requirements above and Troubleshooting below.

---

## Running it

### Option A — CLI (fastest way to verify it works)

```bash
python3 cli.py
```

Runs the full pipeline over the bundled 10-ticket sample (`data/loom_dev_10.csv`) and prints per-ticket classifications, analytics, and an executive summary to stdout. Takes ~5–10 seconds (11 LLM calls: 10 classifications + 1 summary).

Run it against your own CSV:

```bash
python3 cli.py path/to/your_feedback.csv
```

Your CSV needs a `feedback` column at minimum (see Input CSV Schema below) — anything else gets rejected with a clear error, not a crash.

### Option B — API server

```bash
uvicorn main:app --reload --port 8000
```

Then, in another terminal:

```bash
curl -N -X POST http://127.0.0.1:8000/analyze \
  -F "file=@data/loom_dev_10.csv"
```

(`-N` disables curl's output buffering so you see each line as it streams, not all at once at the end.)

Interactive API docs (Swagger UI): open `http://127.0.0.1:8000/docs` in a browser.

The classification pipeline runs inside one request: `POST /analyze`. The response is streamed as newline-delimited JSON (NDJSON): a progress line each time a ticket finishes classification, one "summarizing" line, then a final line carrying the complete result — see Response Shape below. That same call now also persists its result to Postgres before responding, and three small endpoints exist to browse that history: `GET /uploads` (list), `GET /uploads/{id}` (replay one, read-only), `DELETE /uploads/{id}` — see History Endpoints below.

---

## Tests

```bash
pytest
```

80 tests. No real LLM calls, no API key needed to run them — every test that would otherwise touch the network gets a `FakeLLMClient` (`tests/conftest.py`) instead, a duck-typed stand-in exposing the same `structured_call`/`text_call`/`embed` surface as the real `LLMClient`, configured per-test with canned responses (`embed`'s default is a deterministic non-zero dummy vector, so tests that don't care about embedding content still get a valid pgvector-storable value). `LLM_MODEL`/`API_KEY` are still set to dummy values by an autouse fixture, since `utils/config.py` and `LLMClient.__init__` read them unconditionally — they're never actually sent anywhere in a test run.

**Persistence tests use a real local Postgres**, pointed at a separate `loom_test` database (`conftest.py` sets `DATABASE_URL` before `main` is ever imported, so it never touches your `loom_dev`), truncated (`CASCADE`, so `ticket_items` goes with it) by an autouse fixture before every test — no test's saved upload leaks into another's `get_latest_snapshot()`/comparison.

| File | Covers |
|---|---|
| `test_validate.py` | File-level rejections (4001/4002/4003), row skip vs. reject, duplicate-flagging (2nd occurrence only), HTML/Markdown warnings |
| `test_preprocess.py` | HTML/Markdown/whitespace normalization, PII redaction boundaries (email/phone/card/ID by digit count, incl. a parenthesized area code), the long-ticket word-count threshold |
| `test_schemas.py` | theme-belongs-to-category validation, the `Positive Feedback` cross-category exception, `sentiment_score` sign-agreement band, the fallback shape |
| `test_analytics.py` | Denominator rule (percentages against `processed`, success rate against `total_uploaded`), the tie contract (`top_category`/`top_theme` null + leaders list), `fell_back_count`, `additional_issues` excluded from headline distributions |
| `test_classify.py` | The validate → coerce → re-prompt(×1) → fallback sequence: first-try success, recovery via the one guaranteed re-prompt, exhaustion falling back cleanly, a malformed/no-tool-call response going through the same path as a validation failure, and batch ticket-independence |
| `test_llm_client.py` | `_call_with_retry`'s real retry logic against constructed openai SDK exceptions: transient (429/5xx/timeout) retries with backoff then succeeds or exhausts to `TransientLLMError`, auth errors never retry, non-5xx status errors raise `LLMProviderError` without retrying; `embed()`'s empty-input short-circuit, one-vector-per-text-same-order, and that it retries transient errors the same way |
| `test_summarize.py` | `maybe_summarize`'s short-ticket skip / success / LLM-error fallback / empty-response fallback paths; `_fallback_summary_text`'s tie-vs-single-leader rendering; `generate_executive_summary` passing `comparison` through and its own LLM-error fallback |
| `test_api.py` | `POST /analyze` end-to-end through FastAPI's `TestClient` — file-level error responses, a full success-path response shape (parsed off the NDJSON stream's final "result" line), per-row `skipped_rows` detail, row-level `warnings` (e.g. `duplicate_feedback`) reaching the item, real progress events arriving before the result, the week-over-week `comparison` (before/after values, fed into the summary prompt, `theme_sentiment_avg` never reaching it), `GET /uploads` + `GET /uploads/{id}` (including that persisted `items`/`comparison` match what the live upload returned), `DELETE /uploads/{id}` (204, 404 on repeat, cascade-deletes its `ticket_items`), and `POST /chat` (both scopes, `snapshot_id` required for `dashboard` scope, the similarity floor dropping unrelated tickets, `current_upload_facts` included for both scopes including the "most recent upload" rule for `all`, and that `sources` only ever contains tickets the answer actually cited) — all with `LLMClient` monkeypatched |

This deliberately isn't exhaustive coverage — it's a handful of tests per concern covering the scenarios `CLAUDE.md` calls out as load-bearing (the repair sequence, the tie contract, the denominator rule), not every possible input. Add to it as new edge cases turn up.

---

## Input CSV Schema

| Column | Required | Notes |
|---|---|---|
| `feedback` | **Yes** | The raw customer feedback text. Missing this column rejects the whole upload (error `4001`). |
| `id` | No | Your own ticket identifier. If omitted, a stable one is generated per row. |
| `source` | No | e.g. `Email`, `Survey`, `In-App` — passed through, not used in classification. |
| `date` | No | Passed through, not used in classification. |

Empty file / zero rows → rejected (`4002`). A file with a valid `feedback` column but no usable rows after validation → rejected (`4003`). Individual empty/null feedback rows are skipped and counted, not rejected — they don't fail the whole upload.

---

## Response Shape

The HTTP response is a stream of newline-delimited JSON (NDJSON) — one request, one response, no polling and no second endpoint, it just isn't sent as a single blob. Two line types:

```json
{"type": "progress", "stage": "classifying", "done": 3, "total": 10}
{"type": "progress", "stage": "summarizing", "done": 10, "total": 10}
{"type": "result", "data": { /* the full payload below */ }}
```

- Zero or more `progress` lines: one each time a ticket actually finishes classification (`stage: "classifying"`, off the real `as_completed` worker-pool loop in `pipeline/classify.py` — not a fake timer), then exactly one more once the executive-summary call starts (`stage: "summarizing"`).
- Exactly one final `result` line, whose `data` is the complete payload — identical in shape to what this endpoint returned in one shot before streaming existed.

A client that doesn't care about progress can simply read the whole body and parse the last line's `data` — nothing about the final payload changed. `data` shape:

```json
{
  "validation_report": {
    "total_rows": 10,
    "processed": 10,
    "skipped": 0,
    "skip_reasons": {},
    "skipped_rows": [],
    "fell_back_count": 0
  },
  "items": [
    {
      "ticket_id": "D01",
      "feedback_text": "I was charged twice this month for the same subscription...",
      "was_summarized": false,
      "primary_category": "Billing & Payments",
      "primary_theme": "Duplicate Charge",
      "sentiment": "Negative",
      "sentiment_score": -0.7,
      "urgency": "High",
      "actionable": true,
      "additional_issues": [],
      "warnings": []
    }
  ],
  "analytics": {
    "category_distribution": { "...": "..." },
    "theme_frequency": { "...": "..." },
    "theme_sentiment_avg": { "...": "..." },
    "sentiment_distribution": { "...": "..." },
    "urgency_distribution": { "...": "..." },
    "high_urgency_count": 4,
    "actionable_count": 9,
    "fell_back_count": 0,
    "top_category": null,
    "category_leaders": ["Billing & Payments", "Functional Issues"]
  },
  "summary": "Executive summary narrative...",
  "upload_id": 42,
  "uploaded_at": "2026-07-28T12:16:55.545472+05:30",
  "comparison": null
}
```

Notes:
- `top_category` / `top_theme` are `null` when there's a tie — check `category_leaders` / `theme_leaders` instead of assuming a single winner always exists.
- `additional_issues` holds secondary issues on multi-issue tickets (category, theme, urgency only — no sentiment, since sentiment is a whole-ticket property).
- All PII (`[EMAIL]`, `[PHONE]`, `[CARD]`, `[ID]`) is redacted before the LLM ever sees the text; `feedback_text` in the response is the redacted version.
- `validation_report.skipped_rows` lists every skipped row as `{ "ticket_id": "...", "reason": "empty_or_null_feedback" }` — not just the aggregate count/reasons breakdown, so a consumer can show exactly *which* row was dropped, not only how many.
- Each item's `warnings` (e.g. `html_present`, `markdown_present`, `duplicate_feedback`, `long_ticket`) come from row-level validation in `pipeline/validate.py`, never from the model — attached to the classified item after classification via `TicketClassification.model_copy(update={"warnings": ...})` in `api/routes.py`.
- `upload_id` is the row this got saved as in Postgres (`storage/snapshots.py`) — use it with the History Endpoints below. `uploaded_at` is when it was saved.
- `comparison` is `null` only on the very first upload ever. Otherwise it's the diff against whatever was the most recently-saved upload before this one — see below.

### `comparison` shape

Computed by `storage/compare.py` — pure Python over two already-computed `analytics` dicts, no LLM. Every metric carries both the delta AND the before/after absolute values (a bare `-36.7` means nothing without knowing it moved from 70 to 33.3):

```json
{
  "previous_uploaded_at": "2026-07-28T12:15:53+05:30",
  "sentiment_shift_pct": { "Positive": 56.7, "Negative": -36.7, "Neutral": -20.0 },
  "sentiment_pct_before": { "Positive": 10.0, "Negative": 70.0, "Neutral": 20.0 },
  "sentiment_pct_after":  { "Positive": 66.7, "Negative": 33.3, "Neutral": 0.0 },
  "category_shift_pct": { "...": "per-category percentage-point delta" },
  "urgency_shift_count": { "High": -4, "Medium": -2, "Low": 5 },
  "urgency_count_before": { "High": 4, "Medium": 4, "Low": 2 },
  "urgency_count_after":  { "High": 0, "Medium": 2, "Low": 7 },
  "new_themes": ["Integration Request"],
  "disappeared_themes": ["Duplicate Charge"],
  "high_urgency_count_delta": -4, "high_urgency_count_before": 4, "high_urgency_count_after": 0,
  "actionable_pct_delta": -34.4, "actionable_pct_before": 90.0, "actionable_pct_after": 55.6,
  "fell_back_count_delta": 0, "fell_back_count_before": 0, "fell_back_count_after": 0
}
```

`new_themes`/`disappeared_themes` is a plain set difference on `theme_frequency` keys — a theme with 0 tickets this upload vs. ≥1 last upload, nothing more. At small batch sizes this can be sampling variation, not a verified fix or a confirmed new problem — don't over-claim it in any UI built on top of this.

This same `comparison` object is fed into the executive-summary LLM call (`prompts/executive_summary.py`'s `comparison_to_previous_week` field), so `summary` narrates the shift too, with concrete before→after values, grounded only in what's actually in this object.

---

## History Endpoints

**`GET /uploads`** → list every past upload, newest first:

```json
[
  { "id": 2, "uploaded_at": "2026-07-28T12:16:55+05:30", "source_filename": "week2.csv" },
  { "id": 1, "uploaded_at": "2026-07-28T12:15:53+05:30", "source_filename": "week1.csv" }
]
```

**`GET /uploads/{id}`** → replay one upload's full dashboard read-only — same shape as `/analyze`'s `data` (`validation_report`, `items`, `analytics`, `summary`, `comparison`), plus `id`/`uploaded_at`/`source_filename`. Its `comparison` is exactly what was computed and persisted at the time — not recomputed against today's latest upload, which would silently answer a different question ("what changed since the week before *this one*," not "what's changed since the newest upload right now"). 404 if the id doesn't exist.

**`DELETE /uploads/{id}`** → 204 on success, 404 if the id doesn't exist. Cascades to the upload's `ticket_items` rows (FK `ON DELETE CASCADE`) — no separate cleanup needed. No auth/ownership check; fine for a local single-user tool, don't expose this port publicly without adding one.

---

## Chat Endpoint

**`POST /chat`** — ask a free-text question over persisted tickets ("Chat with Tickets" — the dashboard's chat widget). Request:

```json
{ "question": "who is having trouble logging in?", "scope": "dashboard", "snapshot_id": 42 }
```

`scope` is `"dashboard"` (search one upload's tickets — `snapshot_id` required, 400 if missing) or `"all"` (search every upload — `snapshot_id` ignored). Response:

```json
{
  "answer": "Ticket 1 reports being unable to log in with any password. (1)",
  "sources": [
    { "ticket_id": "1", "snapshot_id": 42, "source_filename": "week3.csv", "similarity": 0.49 }
  ]
}
```

**Two data sources, never blended.** Aggregate/statistical/comparison questions ("top category", "what changed since last week") are answered only from `current_upload_facts` — the same Python-computed `analytics`/`comparison` the executive summary narrates from (the snapshot being viewed in `dashboard` scope, or the most recent upload in `all` scope). Content/specific-ticket questions ("who complained about X") are answered only from tickets retrieved by a real `pgvector` cosine-similarity search (`storage/snapshots.py`'s `search_similar_tickets`, using the `<=>` operator) over `ticket_items.embedding`. The model is told which source to use per question type and never lets one stand in for the other.

**`sources` is only what the model actually cited**, not everything retrieval returned — cross-checked against the answer text (`(ticket_id)`, or a bare letter-prefixed id like `D07` as a fallback, since the model doesn't always use the parenthetical format). A greeting or a refusal correctly comes back with `sources: []`.

**Retrieval can legitimately return fewer than `RAG_TOP_K` tickets, or zero** — anything below `RAG_MIN_SIMILARITY` is dropped entirely rather than padded in to fill the limit. See Known Limitations below for a real caveat on how well that similarity floor actually separates relevant from irrelevant.

No uploads exist yet → `{"answer": "No analyzed tickets are available yet to answer from.", "sources": []}`, no LLM call spent. Otherwise the endpoint always tries — even if retrieval alone comes back empty, `current_upload_facts` usually gives the model something to answer from or explicitly refuse with.

---

## Configuration

All via environment variables (`.env`, git-ignored — never commit real keys).

| Variable | Required | Purpose | Default |
|---|---|---|---|
| `LLM_MODEL` | **Yes** | Classification model | — |
| `API_KEY` | **Yes** | OpenAI API key | — |
| `MAX_CONCURRENCY` | No | Parallel in-flight LLM calls | `5` |
| `LONG_TICKET_WORD_LIMIT` | No | Word count that triggers summarization before classification | `300` |
| `MAX_UPLOAD_SIZE` | No | Max CSV upload size in bytes | `5000000` (5 MB) |
| `REQUEST_TIMEOUT` | No | Per-LLM-call timeout (seconds) | `30` |
| `SUMMARY_MODEL` | No | Model used for the executive summary call | falls back to `LLM_MODEL` |
| `LOG_LEVEL` | No | Logging verbosity | `INFO` |
| `DATABASE_URL` | No | Postgres connection string (multi-week persistence) | `postgresql:///loom_dev` |
| `EMBEDDING_MODEL` | No | Model used to embed ticket text for chat retrieval | `text-embedding-3-small` |
| `RAG_TOP_K` | No | Max tickets one chat query can retrieve | `5` |
| `RAG_MIN_SIMILARITY` | No | Minimum cosine similarity to keep a retrieved ticket | `0.2` |

---

## Project Structure

```
backend/
├── api/              # FastAPI routes + request orchestration (main.py mounts this)
├── pipeline/
│   ├── validate.py     # file + row validation
│   ├── preprocess.py   # normalization + PII redaction
│   ├── classify.py     # per-ticket classification: validate -> coerce -> re-prompt -> fallback
│   └── summarize.py    # long-ticket summarization + executive summary
├── analytics/        # deterministic KPI/aggregation — no LLM calls, ever
├── storage/          # Postgres persistence — multi-week history + chat retrieval
│   ├── db.py           # connection + schema (analysis_snapshots, ticket_items incl.
│   │                   # a real pgvector `embedding` column), registers the pgvector
│   │                   # psycopg adapter on every connection
│   ├── snapshots.py     # save/list/get/delete a snapshot + its ticket items,
│   │                   # get_snapshot_facts() (analytics+comparison for chat),
│   │                   # search_similar_tickets() (pgvector `<=>` retrieval)
│   └── compare.py      # pure-Python week-over-week diff (before/after + delta)
├── prompts/           # prompt templates: classification, summarization, executive
│                      # summary, and chat.py (RAG + facts, two-source chat prompt)
├── schemas/           # Pydantic models + canonical taxonomy (schemas/taxonomy.py)
├── services/          # LLM client wrapper (chat completions + embeddings), typed errors
├── utils/             # config loading
├── data/              # sample/dev CSVs (git-ignored — not shipped)
├── tests/             # pytest — see Tests below
├── eval.py            # classification accuracy vs. a hand-labeled answer key
├── cli.py             # run the pipeline over any CSV from the terminal
└── main.py            # FastAPI app, CORS, request timing, Postgres schema init on startup
```

---

## Error Codes

| Code | Meaning |
|---|---|
| `4001` | Missing `feedback` column |
| `4002` | Empty CSV / zero data rows |
| `4003` | No valid feedback rows after validation |

Every classification failure (malformed model output, timeout, validation failure) resolves internally to a fallback shape (`Other` / `Requires Human Review`) — it never raises an HTTP error. The API only returns 4xx for the file-level problems above; everything else always returns `200` with `fell_back_count` reflecting how many tickets needed the safety net. The model is also explicitly instructed to choose `Other` / `Requires Human Review` directly for readable-but-genuinely-confusing tickets (self-contradictory, referencing context never given, incoherent topic-mixing, or an urgent claim immediately denied) — a real, everyday trigger now, not just a rare repair-sequence failure; see `prompts/classification.py`'s vagueness-boundary instruction.

---

## Known Limitations

Documented honestly rather than hidden — see [`docs/Loom_Source_of_Truth.md`](../docs/Loom_Source_of_Truth.md) for full detail:

- Dense multi-issue tickets (3+ distinct problems in one message) have inherent primary-issue ambiguity.
- Two-issue tickets where the second-stated problem reads more severe than the first can occasionally get misordered.
- `New Feature Request` vs `Enhancement Request` is a genuinely fuzzy boundary on some tickets — not force-resolved.
- A domain-owned broken UI element in a category with no matching theme (e.g. a broken button in `Billing & Payments`) currently lands in `Functional Issues` rather than the domain category — safe (schema-valid), not perfectly attributed.
- The `[ID]`/`[PHONE]` PII redaction is a digit-length heuristic — a 7-12 digit non-phone identifier (e.g. an invoice number) gets mislabeled `[PHONE]`. Not a leak, just a labeling nuance (the parenthesized-area-code case, `(555) 123-4567`, *was* a real leak and is fixed).
- Two concurrent `/analyze` calls can both compute their `comparison` against the same prior upload rather than against each other — a non-issue for a single-user local tool, deliberately not fixed (`SELECT ... FOR UPDATE` would be the fix if concurrent uploads become real usage).
- Feedback text now persists at rest in `ticket_items` (previously in-memory only, for one request). Redaction happens before storage same as before, but it's a heuristic, not perfect — worth a retention/deletion policy before this holds real customer data beyond local dev.
- **Chat's similarity floor (`RAG_MIN_SIMILARITY`) doesn't cleanly separate relevant from irrelevant.** OpenAI's `text-embedding-3-small` embeddings have a fairly high baseline cosine similarity between any two pieces of English text — a genuinely relevant ticket has been observed scoring *lower* than an unrelated one on the same query. The floor filters out the clearest noise but isn't a precise relevance classifier for this embedding model.
- **Chat's `sources` citation-matching relies on the model following a format it doesn't always use.** The prompt requires `(ticket_id)`; smaller models sometimes write `Ticket D07:` instead. A fallback regex catches bare letter-prefixed ids (`D07`, `T007`) anywhere in the text, but a dataset using plain numeric ticket ids (`1`, `2`) still needs the parenthetical form to be matched — a citation in some other format on a numeric-id dataset could go unmatched.
- Chat's `scope="all"` always means "the most recent upload's own week-over-week comparison" for any comparison-style question — if a user means an older upload while `all` scope is active, the answer still reflects the latest one.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: 'LLM_MODEL'` on startup | `.env` missing, empty, or not in `backend/` | `cp .env.example .env` and fill in `LLM_MODEL`/`API_KEY` |
| `{"error_code": 4001, ...}` on a CSV you expect to work | No `feedback` column (case-sensitive) | Rename/add a `feedback` column |
| Classification calls fail with an auth error | Bad or expired `API_KEY` | Check the key in `.env`, no retry happens on auth errors by design |
| Port already in use on `uvicorn` | Another process on that port | `uvicorn main:app --reload --port 8001` (or any free port) |
| App fails at startup connecting to Postgres | Postgres isn't running, or `loom_dev` doesn't exist | `brew services start postgresql@16`; `createdb loom_dev` |
| `pytest` fails with a Postgres connection error | `loom_test` database doesn't exist | `createdb loom_test` (tests never touch `loom_dev`) |
| History sidebar empty even after uploading | Checked the wrong database, or Postgres was restarted and lost data | `psql -d loom_dev -c "select id, uploaded_at, source_filename from analysis_snapshots;"` to see what's actually stored |
| `ERROR: extension "vector" is not available` on startup | `pgvector` isn't installed for the Postgres major version you're actually running (a `brew install pgvector` bottle may target a different version) | Build from source against your running server's `pg_config` — see Requirements above |
| Chat always replies "nothing to answer from" even after uploading | Uploads made before `pgvector` was installed have `embedding IS NULL` for every ticket (the column existed as plain JSONB, or the embed call failed) | Upload again after `pgvector` is working — new uploads get real embeddings; old rows aren't retroactively embedded |
