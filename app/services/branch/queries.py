from __future__ import annotations

import sqlite3
from typing import Any

from app.db import get_conn
from app.services.shared.io import normalize_non_content_value


class BranchQueryRepository:
    def list_scope_rows(
        self,
        project_id: int,
        scope_type: str,
        scope_value: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        if conn is not None:
            rows = conn.execute(
                """
                SELECT
                    e.entry_id,
                    e.project_id,
                    e.business_key,
                    e.created_at AS entry_created_at,
                    e.updated_at AS entry_updated_at,
                    v.variant_id,
                    v.file_name,
                    v.source,
                    v.orphaned_at,
                    v.trashed_at,
                    v.trash_until,
                    v.restored_at,
                    v.created_at AS variant_created_at,
                    v.updated_at AS variant_updated_at,
                    b.scope_type,
                    b.scope_value
                FROM scope_bindings b
                JOIN entries e ON e.entry_id = b.entry_id
                JOIN variants v ON v.variant_id = b.variant_id
                WHERE e.project_id = ?
                  AND b.scope_type = ?
                  AND b.scope_value = ?
                  AND v.trashed_at IS NULL
                ORDER BY e.business_key
                """,
                (project_id, scope_type, scope_value),
            ).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(
                    """
                    SELECT
                        e.entry_id,
                        e.project_id,
                        e.business_key,
                        e.created_at AS entry_created_at,
                        e.updated_at AS entry_updated_at,
                        v.variant_id,
                        v.file_name,
                        v.source,
                        v.orphaned_at,
                        v.trashed_at,
                        v.trash_until,
                        v.restored_at,
                        v.created_at AS variant_created_at,
                        v.updated_at AS variant_updated_at,
                        b.scope_type,
                        b.scope_value
                    FROM scope_bindings b
                    JOIN entries e ON e.entry_id = b.entry_id
                    JOIN variants v ON v.variant_id = b.variant_id
                    WHERE e.project_id = ?
                      AND b.scope_type = ?
                      AND b.scope_value = ?
                      AND v.trashed_at IS NULL
                    ORDER BY e.business_key
                    """,
                    (project_id, scope_type, scope_value),
                ).fetchall()
        return self._hydrate_scope_rows(rows)

    def count_scope_entries(self, project_id: int, scope_type: str, scope_value: str) -> int:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM scope_bindings b
                JOIN entries e ON e.entry_id = b.entry_id
                JOIN variants v ON v.variant_id = b.variant_id
                WHERE e.project_id = ?
                  AND b.scope_type = ?
                  AND b.scope_value = ?
                  AND v.trashed_at IS NULL
                """,
                (project_id, scope_type, scope_value),
            ).fetchone()
        return int(row["count"] or 0)

    def release_summary(self, project_id: int) -> dict[str, Any]:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS entry_count,
                    COALESCE((
                        SELECT group_concat(business_key, char(31))
                        FROM (
                            SELECT e2.business_key AS business_key
                            FROM scope_bindings b2
                            JOIN entries e2 ON e2.entry_id = b2.entry_id
                            JOIN variants v2 ON v2.variant_id = b2.variant_id
                            WHERE e2.project_id = ?
                              AND b2.scope_type = 'rel'
                              AND b2.scope_value = 'current'
                              AND v2.trashed_at IS NULL
                            ORDER BY e2.business_key
                            LIMIT 20
                        )
                    ), '') AS business_keys
                FROM scope_bindings b
                JOIN entries e ON e.entry_id = b.entry_id
                JOIN variants v ON v.variant_id = b.variant_id
                WHERE e.project_id = ?
                  AND b.scope_type = 'rel'
                  AND b.scope_value = 'current'
                  AND v.trashed_at IS NULL
                """,
                (project_id, project_id),
            ).fetchone()
        business_keys = [item for item in (row["business_keys"] or "").split(chr(31)) if item]
        return {
            "branch_ref": "rel/current",
            "entry_count": int(row["entry_count"] or 0),
            "business_keys": business_keys,
        }

    def _hydrate_scope_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "entry_id": int(row["entry_id"]),
                "project_id": int(row["project_id"]),
                "business_key": normalize_non_content_value(row["business_key"]),
                "entry_created_at": row["entry_created_at"],
                "entry_updated_at": row["entry_updated_at"],
                "variant_id": int(row["variant_id"]),
                "file_name": normalize_non_content_value(row["file_name"]),
                "source": normalize_non_content_value(row["source"]),
                "orphaned_at": row["orphaned_at"],
                "trashed_at": row["trashed_at"],
                "trash_until": row["trash_until"],
                "restored_at": row["restored_at"],
                "variant_created_at": row["variant_created_at"],
                "variant_updated_at": row["variant_updated_at"],
                "scope_type": row["scope_type"],
                "scope_value": row["scope_value"],
            }
            for row in rows
        ]
