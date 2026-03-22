from __future__ import annotations

import sqlite3
from typing import Any

from app.db import get_conn
from app.services.shared.io import normalize_content_value, normalize_non_content_value


class ReadModelProjectionRepository:
    def list_scope_projection(
        self,
        project_id: int,
        scope_type: str,
        scope_value: str,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    e.entry_id,
                    e.project_id,
                    e.business_key,
                    b.scope_type,
                    b.scope_value,
                    v.variant_id,
                    COALESCE(v.file_name, '') AS file_name,
                    COALESCE(v.source, '') AS source,
                    COALESCE((
                        SELECT target_text
                        FROM variant_translations vt
                        WHERE vt.variant_id = v.variant_id AND vt.lang = ?
                        LIMIT 1
                    ), '') AS lang_target_text,
                    COALESCE((
                        SELECT group_concat(piece, char(31))
                        FROM (
                            SELECT vt.lang || '=' || COALESCE(vt.target_text, '') AS piece
                            FROM variant_translations vt
                            WHERE vt.variant_id = v.variant_id
                            ORDER BY vt.lang
                        )
                    ), '') AS translations_fingerprint,
                    COALESCE((
                        SELECT group_concat(piece, char(31))
                        FROM (
                            SELECT vr.remark_key || '=' || COALESCE(vr.remark_value, '') AS piece
                            FROM variant_remarks vr
                            WHERE vr.variant_id = v.variant_id
                            ORDER BY vr.remark_key
                        )
                    ), '') AS remarks_fingerprint
                FROM scope_bindings b
                JOIN entries e ON e.entry_id = b.entry_id
                JOIN variants v ON v.variant_id = b.variant_id
                WHERE e.project_id = ?
                  AND b.scope_type = ?
                  AND b.scope_value = ?
                  AND v.trashed_at IS NULL
                ORDER BY e.business_key
                """,
                (lang, project_id, scope_type, scope_value),
            ).fetchall()
        return [
            {
                "entry_id": int(row["entry_id"]),
                "project_id": int(row["project_id"]),
                "business_key": normalize_non_content_value(row["business_key"]),
                "scope_type": row["scope_type"],
                "scope_value": row["scope_value"],
                "variant_id": int(row["variant_id"]),
                "file_name": normalize_non_content_value(row["file_name"]),
                "source": normalize_non_content_value(row["source"]),
                "lang_target_text": normalize_content_value(row["lang_target_text"]),
                "translations_fingerprint": row["translations_fingerprint"],
                "remarks_fingerprint": row["remarks_fingerprint"],
            }
            for row in rows
        ]

    def list_scope_variant_rows_for_keys(
        self,
        project_id: int,
        scope_type: str,
        scope_value: str,
        business_keys: list[str],
    ) -> list[dict[str, Any]]:
        if not business_keys:
            return []
        placeholders = ", ".join("?" for _ in business_keys)
        with get_conn() as conn:
            rows = conn.execute(
                f"""
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
                  AND e.business_key IN ({placeholders})
                  AND v.trashed_at IS NULL
                ORDER BY e.business_key
                """,
                [project_id, scope_type, scope_value, *business_keys],
            ).fetchall()
        return self._hydrate_bound_rows(rows)

    def list_master_entry_rows(self, project_id: int, business_key: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
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
                  AND e.business_key = ?
                  AND v.trashed_at IS NULL
                ORDER BY b.scope_type, b.scope_value
                """,
                (project_id, business_key),
            ).fetchall()
        return self._hydrate_bound_rows(rows)

    def search_active_source_rows(self, project_id: int, source: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
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
                  AND v.trashed_at IS NULL
                  AND v.source = ?
                ORDER BY e.business_key, b.scope_type, b.scope_value
                """,
                (project_id, source),
            ).fetchall()
        return self._hydrate_bound_rows(rows)

    def list_active_branch_projections(
        self,
        project_id: int,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                WITH branches AS (
                    SELECT
                        'rel' AS scope_type,
                        'current' AS scope_value,
                        NULL AS version_series,
                        NULL AS is_candidate_release
                    UNION ALL
                    SELECT
                        'dev' AS scope_type,
                        version AS scope_value,
                        version_line AS version_series,
                        is_candidate_release
                    FROM dev_versions
                    WHERE project_id = ? AND promoted_at IS NULL
                )
                SELECT
                    br.scope_type,
                    br.scope_value,
                    br.version_series,
                    br.is_candidate_release,
                    e.entry_id,
                    e.project_id,
                    e.business_key,
                    v.variant_id,
                    COALESCE(v.file_name, '') AS file_name,
                    COALESCE(v.source, '') AS source,
                    COALESCE((
                        SELECT target_text
                        FROM variant_translations vt
                        WHERE vt.variant_id = v.variant_id AND vt.lang = ?
                        LIMIT 1
                    ), '') AS lang_target_text,
                    COALESCE((
                        SELECT group_concat(piece, char(31))
                        FROM (
                            SELECT vt.lang || '=' || COALESCE(vt.target_text, '') AS piece
                            FROM variant_translations vt
                            WHERE vt.variant_id = v.variant_id
                            ORDER BY vt.lang
                        )
                    ), '') AS translations_fingerprint,
                    COALESCE((
                        SELECT group_concat(piece, char(31))
                        FROM (
                            SELECT vr.remark_key || '=' || COALESCE(vr.remark_value, '') AS piece
                            FROM variant_remarks vr
                            WHERE vr.variant_id = v.variant_id
                            ORDER BY vr.remark_key
                        )
                    ), '') AS remarks_fingerprint
                FROM branches br
                LEFT JOIN scope_bindings b
                    ON b.scope_type = br.scope_type
                   AND b.scope_value = br.scope_value
                LEFT JOIN entries e
                    ON e.entry_id = b.entry_id
                   AND e.project_id = ?
                LEFT JOIN variants v
                    ON v.variant_id = b.variant_id
                   AND v.trashed_at IS NULL
                ORDER BY
                    CASE WHEN br.scope_type = 'rel' THEN 0 ELSE 1 END,
                    br.scope_value,
                    e.business_key
                """,
                (project_id, lang, project_id),
            ).fetchall()
        return [
            {
                "branch_ref": f"{row['scope_type']}/{row['scope_value']}",
                "scope_type": row["scope_type"],
                "scope_value": row["scope_value"],
                "version_series": row["version_series"],
                "is_candidate_release": bool(row["is_candidate_release"]) if row["is_candidate_release"] is not None else None,
                "entry_id": int(row["entry_id"]) if row["entry_id"] is not None else None,
                "project_id": int(row["project_id"]) if row["project_id"] is not None else project_id,
                "business_key": normalize_non_content_value(row["business_key"]) if row["business_key"] is not None else "",
                "variant_id": int(row["variant_id"]) if row["variant_id"] is not None else None,
                "file_name": normalize_non_content_value(row["file_name"]),
                "source": normalize_non_content_value(row["source"]),
                "lang_target_text": normalize_content_value(row["lang_target_text"]),
                "translations_fingerprint": row["translations_fingerprint"],
                "remarks_fingerprint": row["remarks_fingerprint"],
            }
            for row in rows
        ]

    def _hydrate_bound_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
