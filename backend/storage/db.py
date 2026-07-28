"""Connection + schema helpers. One connection per call — no pool, matching
CLAUDE.md's "simplicity over speculative production complexity": this
table is written/read once per upload, not a hot path.
"""

import psycopg

from utils.config import load_config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_snapshots (
    id SERIAL PRIMARY KEY,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    validation_report JSONB NOT NULL,
    analytics JSONB NOT NULL,
    summary TEXT NOT NULL
);
-- ADD COLUMN IF NOT EXISTS keeps a table created by an earlier version of
-- this schema (before source_filename/comparison existed) working without
-- a manual migration step — this file is the only source of truth for the
-- schema.
ALTER TABLE analysis_snapshots ADD COLUMN IF NOT EXISTS source_filename TEXT NOT NULL DEFAULT 'upload.csv';
-- Nullable: the first-ever upload has no previous snapshot to diff
-- against. Persisted (not recomputed) so a historical replay can still
-- show "vs the week before it" as it looked at the time — recomputing it
-- against whatever is "latest" today would answer a different question.
ALTER TABLE analysis_snapshots ADD COLUMN IF NOT EXISTS comparison JSONB;

-- One row per ticket per upload — powers the FeedbackExplorer table on a
-- historical replay, and doubles as the groundwork for RAG later (a
-- `pgvector` embedding column can be added here directly; `item` already
-- holds the redacted feedback_text an embedding would be computed over).
-- ON DELETE CASCADE: deleting an upload deletes its tickets with it, no
-- separate cleanup step.
CREATE TABLE IF NOT EXISTS ticket_items (
    id SERIAL PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES analysis_snapshots(id) ON DELETE CASCADE,
    ticket_id TEXT NOT NULL,
    item JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ticket_items_snapshot_id ON ticket_items (snapshot_id);
"""


def get_connection() -> psycopg.Connection:
    config = load_config()
    return psycopg.connect(config.database_url)


def ensure_schema() -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(_SCHEMA)
        conn.commit()
