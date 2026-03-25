from __future__ import annotations

import sqlite3

from app.db import get_conn
from app.services.project.service import ProjectService
from app.services.shared.io import normalize_content_value, normalize_non_content_value
from app.services.variant.pivot import derive_pivot_sync_status
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

    def list_pivot_sync_statuses(
        self,
        project_id: int,
        variant_ids: list[int],
        lang: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, object]:
        schema = self.projects.get_schema(project_id)
        pivot_lang = schema["translation_pivots"].get(lang)
        if not pivot_lang or not variant_ids:
            return {"pivot_lang": pivot_lang, "statuses": {}}
        placeholders = ", ".join("?" for _ in variant_ids)
        query = f"""
            SELECT
                v.variant_id,
                child.target_text AS child_text,
                parent.target_text AS parent_text,
                sync.pivot_fingerprint_at_sync
            FROM variants v
            JOIN entries e ON e.entry_id = v.entry_id
            LEFT JOIN variant_translations child
                ON child.variant_id = v.variant_id
               AND child.lang = ?
            LEFT JOIN variant_translations parent
                ON parent.variant_id = v.variant_id
               AND parent.lang = ?
            LEFT JOIN variant_translation_sync_state sync
                ON sync.variant_id = v.variant_id
               AND sync.lang = ?
            WHERE e.project_id = ?
              AND v.variant_id IN ({placeholders})
        """
        params = [lang, pivot_lang, lang, project_id, *variant_ids]
        if conn is not None:
            rows = conn.execute(query, params).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(query, params).fetchall()
        statuses = {
            int(row["variant_id"]): derive_pivot_sync_status(
                child_text=normalize_content_value(row["child_text"]),
                parent_text=normalize_content_value(row["parent_text"]),
                pivot_fingerprint_at_sync=row["pivot_fingerprint_at_sync"],
            )
            for row in rows
        }
        return {"pivot_lang": pivot_lang, "statuses": statuses}
