# Loom Frontend

React + TypeScript dashboard for Loom. Uploads a CSV, calls the backend's single `POST /analyze` endpoint once, and renders the returned payload — KPIs, distribution charts, an executive summary, and a searchable/sortable feedback table, exportable as a PDF report. No AI runs in the frontend; every number on screen is a direct read of data the backend already computed.

Full design rationale: [`docs/Loom_Source_of_Truth.md`](../docs/Loom_Source_of_Truth.md).

---

## Requirements

- Node.js 18+ (tested on Node 22 and 26)
- npm 9+ (ships with Node)
- The Loom backend running and reachable (see `backend/README.md`) — the frontend renders nothing real without it

---

## Setup (cold start)

Run these from the `frontend/` directory.

```bash
# 1. Install dependencies
npm install

# 2. Configure environment
cp .env.example .env
```

`.env` only needs one variable, and it already has a working default for local development:

```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Change it if your backend runs somewhere other than the default `uvicorn main:app --port 8000` from `backend/README.md`. **Do not commit `.env`** if you ever put anything environment-specific in it — it's git-ignored on purpose (though for this project it never holds a secret; the backend holds the API key, not the frontend).

---

## Running it

Start the backend first — see `backend/README.md` (`uvicorn main:app --reload --port 8000` from `backend/`). Nothing in the frontend works without it; the dashboard makes exactly one network call, `POST /analyze`, and has no fallback data source.

```bash
npm run dev
```

Vite prints a local URL (default `http://localhost:5173`). Open it, click **Upload a CSV**, and pick a file with a `feedback` column (see `backend/README.md`'s Input CSV Schema — the frontend doesn't repeat that validation, the backend is the single source of truth for what's a valid upload).

If the backend isn't running or isn't reachable at `VITE_API_BASE_URL`, the upload will fail with a readable error banner (not a silent hang or a blank screen) — see Troubleshooting below.

---

## Build, Test, Lint

```bash
npm run build   # tsc --build (type-check) + vite build (production bundle) → dist/
npm test        # vitest — see "Why the tests need a stubbed browser" below
npm run lint    # oxlint
```

`npm run build` is the fastest way to catch a type error or a broken import — it always runs `tsc -b` before bundling, so a build failure is a real compile error, not a bundler quirk.

### Why the tests need a stubbed browser

There's no real browser in this project's dev/CI environment, so the test suite runs on `vitest` + `jsdom`. jsdom has no layout engine and is missing a few browser APIs the app actually uses — without stubbing them, entire chunks of the UI (charts, in particular) would silently render as empty `<div>`s instead of the real thing, and tests would pass without testing anything. `src/test/setup.ts` stubs:

| API | Why it's needed |
|---|---|
| `ResizeObserver` | Recharts' `ResponsiveContainer` waits for a resize callback to learn its size; jsdom has no `ResizeObserver` at all, so the callback must fire manually with a real size or every chart stays at 0×0 and renders nothing. |
| `HTMLElement.offsetWidth/offsetHeight` | jsdom reports `0` for both; stubbed to a fixed size so the container above actually has something to measure. |
| `window.matchMedia` | Used by the dark-mode toggle (system-preference default) and `prefers-reduced-motion` checks; jsdom doesn't implement it at all. |
| `Element.prototype.scrollIntoView` | Used when clicking a chart bar scrolls the ticket table into view; jsdom doesn't implement it. |

The test suite itself drives real interactions through the real component tree — file upload, search, sort, filter, expand a row, **click an actual rendered SVG chart bar and assert the table narrows** — against `/analyze` response payloads captured verbatim from the live local backend (`src/test/fixtures/`), not hand-guessed mocks. If you add a component that touches a browser API jsdom doesn't have, the fix belongs in `src/test/setup.ts`, not in the component.

---

## Project Structure

```
src/
├── api/
│   └── analyzeClient.ts       # the one POST /analyze call; throws AnalyzeApiError with
│                              # the backend's error_code/message on a 4xx
├── hooks/
│   └── useAnalyze.ts          # owns request status (idle/loading/success/error) + the
│                              # response payload — no polling, no persistence
├── types/
│   ├── taxonomy.ts            # Category/Theme/Sentiment/Urgency string unions, mirrored
│   │                          # character-for-character from backend/schemas/taxonomy.py
│   └── analyze.ts             # full /analyze response shape (ValidationReport,
│                              # TicketClassification, Analytics, AnalyzeResponse)
├── components/
│   ├── Nav.tsx                # top bar: brand, dark-mode toggle, upload trigger
│   ├── AmbientStatus.tsx      # borderless status line below Nav (batch name + stage word)
│   ├── IdleLanding.tsx        # pre-upload screen: hero, pipeline steps, capability grid
│   ├── ValidationBanner.tsx   # total/processed/skipped rows, fell_back_count
│   ├── KpiCards.tsx           # the 10 headline KPIs
│   ├── SummaryPanel.tsx       # renders the backend's executive summary verbatim (clamped)
│   ├── FeedbackExplorer.tsx   # ticket table: search, sort, category/theme/sentiment/
│   │                          # urgency filters, expandable rows with additional_issues
│   ├── ExportButton.tsx       # exports the current analysis as a PDF report
│   │                          # (KPIs + distributions + summary — see utils/exportReport.ts)
│   └── charts/
│       ├── DistributionBarChart.tsx      # shared Recharts bar chart (labels, tooltip,
│       │                                 # optional click-to-filter)
│       ├── CategoryDistributionChart.tsx
│       ├── ThemeFrequencyChart.tsx
│       ├── SentimentDistributionChart.tsx
│       └── UrgencyBreakdownChart.tsx
├── pages/
│   └── DashboardPage.tsx      # composes everything above into the single dashboard view
├── utils/
│   ├── colors.ts              # ONE category/sentiment/urgency color map — every chart
│   │                          # and the table import from here, never a local hex value
│   └── exportReport.ts        # builds the PDF report (jsPDF + jspdf-autotable)
│                              # from the same AnalyzeResponse already in state
├── test/
│   ├── setup.ts               # jsdom stubs (see above)
│   └── fixtures/              # real /analyze responses captured from the live backend
├── index.css                  # design tokens (light + dark) as CSS custom properties,
│                              # consumed as Tailwind utilities (bg-surface, text-ink, ...)
├── App.tsx
└── main.tsx
```

See `frontend/CLAUDE.md` (gitignored, internal) for the full operational spec this was built against — where this README and the code ever disagree with it, treat `CLAUDE.md` as the record of intent and this README as what's actually true today.

---

## What the frontend renders — and what it never does

Mirrors `backend/README.md`'s Response Shape exactly (the frontend's `types/analyze.ts` is typed against it field-for-field):

- **KPIs** (`KpiCards`): total feedback, skipped rows, positive/negative %, top category/theme (or the tied leaders, when there's no single winner), high-urgency count, actionable %, needs-review count, processing success rate.
- **Charts** (`components/charts/`): category distribution, top themes, sentiment split, urgency breakdown — each a horizontal bar chart, each fully labeled, each clickable (category/theme) to filter the ticket table below.
- **Executive summary** (`SummaryPanel`): the backend's grounded narrative, rendered as-is.
- **Ticket table** (`FeedbackExplorer`): every processed ticket, searchable over feedback text, sortable, filterable, expandable to show `additional_issues`.
- **Export** (`ExportButton`): a one-click PDF report of the KPIs, the four distributions, and the executive summary — deliberately not a dump of every ticket (that's already in the table above), built client-side from the same payload, nothing recomputed.

What it deliberately does **not** do (see `frontend/CLAUDE.md`'s "Do NOT" list for the full set):
- Never calls an LLM or any AI service — it only renders what `/analyze` already returned.
- Never makes more than one backend call per uploaded file — no polling, no `upload_id`, no second request.
- Never recomputes an analytic the backend already sent (e.g. an average `sentiment_score`) — it displays backend-computed numbers, or at most a simple share computed against `processed` (never against `total_rows`).
- Never persists anything client-side — a new upload just replaces the in-memory payload; refreshing the page returns to the empty state.

---

## Configuration

| Variable | Required | Purpose | Default |
|---|---|---|---|
| `VITE_API_BASE_URL` | No | Base URL the frontend calls for `POST /analyze` | `http://127.0.0.1:8000` |

That's the only configuration surface. There's no API key, no build-time secret, no feature flags — the frontend is a pure client of one backend endpoint.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Upload spins and then shows "Could not reach the Loom backend..." | Backend isn't running, or isn't reachable at `VITE_API_BASE_URL` | Start it (`backend/README.md`) and confirm `curl http://127.0.0.1:8000/docs` returns `200` |
| Error banner shows a `4001`/`4002`/`4003` message | The CSV itself is invalid (missing `feedback` column, empty file, or no usable rows) | Fix the CSV per `backend/README.md`'s Input CSV Schema — this is the backend's validation surfacing correctly, not a frontend bug |
| CORS error in the browser console | Backend's CORS policy doesn't allow the frontend's origin | Backend currently allows `*` for local/demo use (see `backend/CLAUDE.md`) — if that's been locked down, add the frontend's origin |
| Chart looks empty / "No data to show" | `analytics` has no entries for that distribution (e.g. zero processed tickets isn't reachable via a 200 response, but an all-one-category batch will legitimately show a single bar) | Confirm the payload in the Network tab actually has non-empty `category_distribution`/`theme_frequency`/etc. |
| A chart test renders nothing / can't find an SVG bar in a new test | jsdom needs the stubs in `src/test/setup.ts` (see "Why the tests need a stubbed browser") | Make sure the test imports through the normal Vitest setup (it's wired globally via `vitest.config.ts`'s `setupFiles`) rather than bypassing it |
| Port already in use on `vite` | Another process on the default port | `npm run dev -- --port 5174` (or any free port) |
| `tsc -b` fails referencing a `.test.tsx` file | Test files are included in `tsconfig.app.json`'s `src` include and type-checked like any other source file | Fix the type error in the test — it's a real one, not a build-config issue |
