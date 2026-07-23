# Loom Backend

AI-powered customer feedback classification. Upload a CSV of raw customer feedback, get back per-ticket classification (category, theme, sentiment, urgency, actionable), deterministic analytics, and a grounded executive summary — all in one request.

Full design rationale: [`docs/Loom_Source_of_Truth.md`](../docs/Loom_Source_of_Truth.md).

---

## Requirements

- Python 3.11+ (tested on 3.12)
- An OpenAI API key (classification runs on `gpt-4o-mini` by default — see Configuration)

---

## Setup (cold start)

Run these from the `backend/` directory.

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
```

Now open `.env` and fill in at minimum:

```
LLM_MODEL=gpt-4o-mini
API_KEY=sk-...your-real-key...
```

Everything else in `.env` has a working default (see Configuration below) — you only need to set `LLM_MODEL` and `API_KEY` to get started. **Do not commit `.env`** — it's git-ignored on purpose.

If you skip this step, both the CLI and the API will fail immediately at startup with `KeyError: 'LLM_MODEL'` — that error means `.env` is missing or empty, not a bug.

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
curl -X POST http://127.0.0.1:8000/analyze \
  -F "file=@data/loom_dev_10.csv"
```

Interactive API docs (Swagger UI): open `http://127.0.0.1:8000/docs` in a browser.

There is exactly one endpoint: `POST /analyze`. The system is stateless — no database, no session, the whole pipeline runs inside that one request and returns everything in one JSON payload.

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

```json
{
  "validation_report": {
    "total_rows": 10,
    "processed": 10,
    "skipped": 0,
    "skip_reasons": {},
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
      "additional_issues": []
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
  "summary": "Executive summary narrative..."
}
```

Notes:
- `top_category` / `top_theme` are `null` when there's a tie — check `category_leaders` / `theme_leaders` instead of assuming a single winner always exists.
- `additional_issues` holds secondary issues on multi-issue tickets (category, theme, urgency only — no sentiment, since sentiment is a whole-ticket property).
- All PII (`[EMAIL]`, `[PHONE]`, `[CARD]`, `[ID]`) is redacted before the LLM ever sees the text; `feedback_text` in the response is the redacted version.

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
├── prompts/           # prompt templates (classification + summarization)
├── schemas/           # Pydantic models + canonical taxonomy (schemas/taxonomy.py)
├── services/          # LLM client wrapper, typed errors
├── utils/             # config loading
├── data/              # sample/dev CSVs (git-ignored — not shipped)
├── cli.py             # run the pipeline over any CSV from the terminal
└── main.py            # FastAPI app, CORS, request timing
```

---

## Error Codes

| Code | Meaning |
|---|---|
| `4001` | Missing `feedback` column |
| `4002` | Empty CSV / zero data rows |
| `4003` | No valid feedback rows after validation |

Every classification failure (malformed model output, timeout, validation failure) resolves internally to a fallback shape (`Other` / `Requires Human Review`) — it never raises an HTTP error. The API only returns 4xx for the file-level problems above; everything else always returns `200` with `fell_back_count` reflecting how many tickets needed the safety net.

---

## Known Limitations

Documented honestly rather than hidden — see [`docs/Loom_Source_of_Truth.md`](../docs/Loom_Source_of_Truth.md) for full detail:

- Dense multi-issue tickets (3+ distinct problems in one message) have inherent primary-issue ambiguity.
- Two-issue tickets where the second-stated problem reads more severe than the first can occasionally get misordered.
- `New Feature Request` vs `Enhancement Request` is a genuinely fuzzy boundary on some tickets — not force-resolved.
- A domain-owned broken UI element in a category with no matching theme (e.g. a broken button in `Billing & Payments`) currently lands in `Functional Issues` rather than the domain category — safe (schema-valid), not perfectly attributed.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: 'LLM_MODEL'` on startup | `.env` missing, empty, or not in `backend/` | `cp .env.example .env` and fill in `LLM_MODEL`/`API_KEY` |
| `{"error_code": 4001, ...}` on a CSV you expect to work | No `feedback` column (case-sensitive) | Rename/add a `feedback` column |
| Classification calls fail with an auth error | Bad or expired `API_KEY` | Check the key in `.env`, no retry happens on auth errors by design |
| Port already in use on `uvicorn` | Another process on that port | `uvicorn main:app --reload --port 8001` (or any free port) |
