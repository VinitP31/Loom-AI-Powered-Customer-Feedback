"""CRUD over analysis_snapshots + ticket_items — save each upload's
already-computed result (aggregate + per-ticket items), list past uploads
(for the history sidebar), fetch one by id (read-only replay, now
including its tickets), and fetch the most recent one (for the "vs last
week" diff, computed by compare.py before the current upload is saved —
items are never needed for that, so get_latest_snapshot() skips them).
"""

from datetime import datetime
from typing import TypedDict

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


def save_snapshot(
    validation_report: dict,
    analytics: dict,
    summary: str,
    source_filename: str,
    items: list[dict],
    comparison: dict | None = None,
) -> SnapshotSummary:
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
                "INSERT INTO ticket_items (snapshot_id, ticket_id, item) VALUES (%s, %s, %s)",
                [(snapshot_id, item["ticket_id"], Json(item)) for item in items],
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


def delete_snapshot(snapshot_id: int) -> bool:
    """Returns False if no row with that id existed (caller 404s). Its
    ticket_items rows go with it via ON DELETE CASCADE — no separate
    cleanup query needed."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM analysis_snapshots WHERE id = %s", (snapshot_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
