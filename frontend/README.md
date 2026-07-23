# Loom Frontend

React + TypeScript dashboard for Loom. Uploads a CSV, calls the backend's
single `POST /analyze` endpoint once, and renders the returned payload —
KPIs, distribution charts, an executive summary, and a searchable/sortable
feedback table. No AI runs in the frontend; everything here is a read of
data the backend already computed.

## Setup

```bash
npm install
cp .env.example .env   # points at the local backend by default
```

## Run

Start the backend first (see `backend/README.md`), then:

```bash
npm run dev
```

Open the printed local URL. Upload a CSV with a `feedback` column (an
`id` column is optional).

## Test

```bash
npm run build   # tsc type-check + production build
npm test        # vitest — integration tests drive real component
                # interactions (upload, search, filter, expand) against
                # /analyze payloads captured from the live backend
npm run lint    # oxlint
```

## Project structure

```
src/
├── api/          # analyzeClient.ts — the one POST /analyze call
├── hooks/        # useAnalyze() — request status + payload state
├── types/        # taxonomy.ts + analyze.ts, mirroring the backend contract
├── components/   # UploadPanel, KpiCards, ValidationBanner, SummaryPanel,
│                 # FeedbackExplorer, charts/
├── pages/        # DashboardPage — the single dashboard view
├── utils/        # colors.ts — one category/sentiment/urgency color map,
│                 # reused by every chart and the table
└── test/         # vitest setup + fixtures captured from the live backend
```

See `frontend/CLAUDE.md` (gitignored, internal) for the full operational
spec this was built against.

## Configuration

`VITE_API_BASE_URL` (`.env`) — base URL of the backend. Defaults to
`http://127.0.0.1:8000`, matching `backend/README.md`'s local dev setup.
