"""CRUD over analysis_snapshots + ticket_items — save each upload's
already-computed result (aggregate + per-ticket items), list past uploads
(for the history sidebar), fetch one by id (read-only replay, now
including its tickets), and fetch the most recent one (for the "vs last
week" diff, computed by compare.py before the current upload is saved —
items are never needed for that, so get_latest_snapshot() skips them).
"""

from datetime import datetime
from typing import TypedDict

from pgvector import Vector
from psycopg.types.json import Json

from storage.db import get_connection


class SnapshotSummary(TypedDict):
    id: int
    uploaded_at: datetime
    source_filename: str


class Snapshot(SnapshotSummary):
    validation_report: dict
    analytics: dict
    summary: str
    comparison: dict | None


class SnapshotWithItems(Snapshot):
    items: list[dict]


class SnapshotFacts(TypedDict):
    analytics: dict
    comparison: dict | None
    uploaded_at: datetime


def get_snapshot_facts(snapshot_id: int) -> SnapshotFacts | None:
    """analytics + comparison only, for chat (prompts/chat.py) — the same
    Python-computed facts the executive summary narrates from, not a RAG
    retrieval. No items/validation_report fetched; this is never the
    heavy per-ticket payload."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT analytics, comparison, uploaded_at FROM analysis_snapshots WHERE id = %s",
            (snapshot_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {"analytics": row[0], "comparison": row[1], "uploaded_at": row[2]}


def save_snapshot(
    validation_report: dict,
    analytics: dict,
    summary: str,
    source_filename: str,
    items: list[dict],
    comparison: dict | None = None,
    embeddings: list[list[float] | None] | None = None,
) -> SnapshotSummary:
    """`embeddings`, if given, must be the same length and order as
    `items` — one entry per ticket, or None for a ticket whose embedding
    call failed (see api/routes.py). Omitted entirely, every ticket is
    stored with no embedding (excluded from chat retrieval, nothing else
    breaks)."""
    if embeddings is None:
        embeddings = [None] * len(items)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO analysis_snapshots (validation_report, analytics, summary, source_filename, comparison)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, uploaded_at, source_filename
            """,
            (
                Json(validation_report),
                Json(analytics),
                summary,
                source_filename,
                Json(comparison) if comparison is not None else None,
            ),
        )
        row = cur.fetchone()
        snapshot_id = row[0]

        if items:
            cur.executemany(
                "INSERT INTO ticket_items (snapshot_id, ticket_id, item, embedding) VALUES (%s, %s, %s, %s)",
                [
                    (snapshot_id, item["ticket_id"], Json(item), Vector(embedding) if embedding is not None else None)
                    for item, embedding in zip(items, embeddings)
                ],
            )

        conn.commit()
        return {"id": snapshot_id, "uploaded_at": row[1], "source_filename": row[2]}


def get_latest_snapshot() -> Snapshot | None:
    """Most recent snapshot saved so far — called BEFORE the current
    upload is saved, so it never returns the current upload itself.
    Items are never needed for the week-over-week diff (that's computed
    over `analytics` only), so this deliberately doesn't fetch them."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, uploaded_at, source_filename, validation_report, analytics, summary, comparison
            FROM analysis_snapshots
            ORDER BY uploaded_at DESC, id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "uploaded_at": row[1],
            "source_filename": row[2],
            "validation_report": row[3],
            "analytics": row[4],
            "summary": row[5],
            "comparison": row[6],
        }


def list_snapshots() -> list[SnapshotSummary]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, uploaded_at, source_filename FROM analysis_snapshots ORDER BY uploaded_at DESC, id DESC"
        )
        return [{"id": row[0], "uploaded_at": row[1], "source_filename": row[2]} for row in cur.fetchall()]


def get_snapshot(snapshot_id: int) -> SnapshotWithItems | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, uploaded_at, source_filename, validation_report, analytics, summary, comparison
            FROM analysis_snapshots
            WHERE id = %s
            """,
            (snapshot_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None

        cur.execute(
            "SELECT item FROM ticket_items WHERE snapshot_id = %s ORDER BY id",
            (snapshot_id,),
        )
        items = [item_row[0] for item_row in cur.fetchall()]

        return {
            "id": row[0],
            "uploaded_at": row[1],
            "source_filename": row[2],
            "validation_report": row[3],
            "analytics": row[4],
            "summary": row[5],
            "comparison": row[6],
            "items": items,
        }


class RankedTicket(TypedDict):
    ticket_id: str
    item: dict
    snapshot_id: int
    source_filename: str
    uploaded_at: datetime
    similarity: float


def search_similar_tickets(
    query_embedding: list[float], snapshot_id: int | None, top_k: int, min_similarity: float = 0.0
) -> list[RankedTicket]:
    """RAG retrieval for the /chat endpoint. Ranks tickets by pgvector's
    `<=>` cosine-distance operator directly in SQL — real pgvector, not a
    Python-side scan. similarity = 1 - distance (`<=>` returns distance,
    0=identical .. 2=opposite). snapshot_id=None searches every upload
    ("all history" scope); a given id scopes to just that one dashboard.
    Tickets whose embedding call failed at ingest (embedding IS NULL) are
    excluded by the JOIN semantics of `<=>` against them (never matches).
    `min_similarity` drops anything below the bar entirely — can return
    fewer than top_k rows, including zero, rather than padding out with
    unrelated tickets just to fill the limit. No ANN index yet — see
    storage/db.py's schema comment — so this is an exact sequential scan
    ordered by distance, fine at current scale."""
    with get_connection() as conn, conn.cursor() as cur:
        query = """
            SELECT * FROM (
                SELECT t.ticket_id, t.item, s.id AS snapshot_id, s.source_filename, s.uploaded_at,
                       1 - (t.embedding <=> %s) AS similarity
                FROM ticket_items t
                JOIN analysis_snapshots s ON s.id = t.snapshot_id
                WHERE t.embedding IS NOT NULL
        """
        params: list = [Vector(query_embedding)]
        if snapshot_id is not None:
            query += " AND t.snapshot_id = %s"
            params.append(snapshot_id)
        query += """
            ) ranked
            WHERE similarity >= %s
            ORDER BY similarity DESC
            LIMIT %s
        """
        params.extend([min_similarity, top_k])

        cur.execute(query, params)
        return [
            {
                "ticket_id": row[0],
                "item": row[1],
                "snapshot_id": row[2],
                "source_filename": row[3],
                "uploaded_at": row[4],
                "similarity": row[5],
            }
            for row in cur.fetchall()
        ]


def delete_snapshot(snapshot_id: int) -> bool:
    """Returns False if no row with that id existed (caller 404s). Its
    ticket_items rows go with it via ON DELETE CASCADE — no separate
    cleanup query needed."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM analysis_snapshots WHERE id = %s", (snapshot_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
