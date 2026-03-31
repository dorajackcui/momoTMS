from __future__ import annotations

import sqlite3

from app.db import get_conn
from app.services.project.service import ProjectService
from app.services.shared.io import normalize_content_value, normalize_non_content_value
from app.services.variant.records import FillCandidateRecord


class FillQueryService:
    def __init__(self, projects: ProjectService | None = None) -> None:
        self.projects = projects or ProjectService()

    def list_fill_candidates(
        self,
        project_id: int,
        lang: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[FillCandidateRecord]:
        query = """
            SELECT
                e.business_key,
                v.source,
                v.variant_id,
                v.orphaned_at,
                v.trashed_at,
                v.updated_at,
                vt.target_text
            FROM variants v
            JOIN entries e ON e.entry_id = v.entry_id
            LEFT JOIN variant_translations vt
                ON vt.variant_id = v.variant_id
               AND vt.lang = ?
            WHERE e.project_id = ?
            ORDER BY
                e.business_key,
                v.source,
                CASE WHEN v.trashed_at IS NULL THEN 0 ELSE 1 END,
                v.updated_at DESC,
                v.variant_id DESC
        """
        params = (lang, project_id)
        if conn is not None:
            rows = conn.execute(query, params).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(query, params).fetchall()
        return [
            {
                "business_key": normalize_non_content_value(row["business_key"]),
                "source": normalize_non_content_value(row["source"]),
                "target_text": normalize_content_value(row["target_text"]),
                "variant_id": int(row["variant_id"]),
                "orphaned_at": row["orphaned_at"],
                "trashed_at": row["trashed_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
