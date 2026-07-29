"""Connection + schema helpers. One connection per call — no pool, matching
CLAUDE.md's "simplicity over speculative production complexity": this
table is written/read once per upload, not a hot path.
"""

import psycopg
from pgvector.psycopg import register_vector

from utils.config import load_config

_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

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
-- historical replay, and (via `embedding`) is what the RAG chat feature
-- searches over. ON DELETE CASCADE: deleting an upload deletes its
-- tickets with it, no separate cleanup step.
CREATE TABLE IF NOT EXISTS ticket_items (
    id SERIAL PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES analysis_snapshots(id) ON DELETE CASCADE,
    ticket_id TEXT NOT NULL,
    item JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ticket_items_snapshot_id ON ticket_items (snapshot_id);
-- Real pgvector column — no fixed dimension, so it accepts whatever
-- EMBEDDING_MODEL currently produces without a schema change if that
-- model is ever swapped. Nullable: an embedding call can fail without
-- blocking the upload (same degrade-gracefully pattern as
-- summarization); a null embedding is just excluded from chat retrieval.
-- No ANN index (ivfflat/hnsw) yet — plain `<=>` cosine-distance scan
-- (services/rag.py) is exact and fast enough at current scale (a
-- handful of weekly snapshots). Add an index once history grows large
-- enough for a full scan to matter (see Future Scope in docs).
ALTER TABLE ticket_items ADD COLUMN IF NOT EXISTS embedding vector;
"""


def get_connection() -> psycopg.Connection:
    config = load_config()
    conn = psycopg.connect(config.database_url)
    register_vector(conn)
    return conn


def ensure_schema() -> None:
    # Plain connect, not get_connection(): register_vector() needs the
    # `vector` type to already exist, but CREATE EXTENSION IF NOT EXISTS
    # below is what creates it on a brand new database — chicken-and-egg
    # if this used get_connection(). Every other caller in the app runs
    # after ensure_schema() (main.py calls it at startup), so
    # get_connection() can always assume the extension is already there.
    config = load_config()
    with psycopg.connect(config.database_url) as conn, conn.cursor() as cur:
        cur.execute(_SCHEMA)
        conn.commit()
