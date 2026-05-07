from __future__ import annotations

from collections import defaultdict
import sqlite3
from typing import Any

from app.db import get_conn
from app.services.shared.io import (
    normalize_content_map,
    normalize_content_value,
    normalize_non_content_map,
    normalize_non_content_value,
)
from app.services.shared.sql import iter_sql_chunks
from app.services.variant.records import VariantRecord


class _VariantStore:
    def create(
        self,
        entry_id: int,
        file_name: str,
        source: str,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        if conn is not None:
            cur = conn.execute(
                """
                INSERT INTO variants(
                    entry_id,
                    file_name,
                    source,
                    orphaned_at,
                    pivot_status,
                    pivot_status_updated_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (entry_id, file_name, source, timestamp, "init", timestamp, timestamp, timestamp),
            )
            return int(cur.lastrowid)
        with get_conn() as local_conn:
            cur = local_conn.execute(
                """
                INSERT INTO variants(
                    entry_id,
                    file_name,
                    source,
                    orphaned_at,
                    pivot_status,
                    pivot_status_updated_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (entry_id, file_name, source, timestamp, "init", timestamp, timestamp, timestamp),
            )
        return int(cur.lastrowid)

    def update(
        self,
        variant_id: int,
        file_name: str,
        source: str,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            conn.execute(
                """
                UPDATE variants
                SET file_name = ?,
                    source = ?,
                    updated_at = ?
                WHERE variant_id = ?
                """,
                (file_name, source, timestamp, variant_id),
            )
            return
        with get_conn() as local_conn:
            self.update(
                variant_id,
                file_name,
                source,
                timestamp,
                conn=local_conn,
            )

    def overwrite_translations(
        self,
        variant_id: int,
        translations: dict[str, str],
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            conn.execute(
                "DELETE FROM variant_translations WHERE variant_id = ?",
                (variant_id,),
            )
            for lang, target_text in translations.items():
                conn.execute(
                    """
                    INSERT INTO variant_translations(variant_id, lang, target_text, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (variant_id, lang, target_text, timestamp),
                )
            return
        with get_conn() as local_conn:
            self.overwrite_translations(variant_id, translations, timestamp, conn=local_conn)

    def overwrite_remarks(
        self,
        variant_id: int,
        remarks: dict[str, str],
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            conn.execute(
                "DELETE FROM variant_remarks WHERE variant_id = ?",
                (variant_id,),
            )
            for remark_key, remark_value in remarks.items():
                conn.execute(
                    """
                    INSERT INTO variant_remarks(variant_id, remark_key, remark_value, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (variant_id, remark_key, remark_value, timestamp),
                )
            return
        with get_conn() as local_conn:
            self.overwrite_remarks(variant_id, remarks, timestamp, conn=local_conn)

    def get(self, variant_id: int, conn: sqlite3.Connection | None = None) -> VariantRecord | None:
        if conn is not None:
            row = conn.execute(
                "SELECT * FROM variants WHERE variant_id = ?",
                (variant_id,),
            ).fetchone()
            if not row:
                return None
            return self._hydrate_rows([row], conn=conn)[0]
        with get_conn() as local_conn:
            row = local_conn.execute(
                "SELECT * FROM variants WHERE variant_id = ?",
                (variant_id,),
            ).fetchone()
            if not row:
                return None
            return self._hydrate_rows([row], conn=local_conn)[0]

    def get_many(
        self,
        variant_ids: list[int],
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, VariantRecord]:
        unique_ids = sorted({int(variant_id) for variant_id in variant_ids})
        if not unique_ids:
            return {}
        if conn is not None:
            rows = self._select_rows_by_variant_ids(unique_ids, conn=conn)
            return {
                int(variant["variant_id"]): variant
                for variant in self._hydrate_rows(rows, conn=conn)
            }
        with get_conn() as local_conn:
            rows = self._select_rows_by_variant_ids(unique_ids, conn=local_conn)
            return {
                int(variant["variant_id"]): variant
                for variant in self._hydrate_rows(rows, conn=local_conn)
            }

    def get_active_by_entry_and_source(
        self,
        entry_id: int,
        source: str,
        conn: sqlite3.Connection | None = None,
    ) -> VariantRecord | None:
        if conn is not None:
            rows = conn.execute(
                """
                SELECT *
                FROM variants
                WHERE entry_id = ?
                  AND source = ?
                  AND trashed_at IS NULL
                ORDER BY variant_id
                """,
                (entry_id, source),
            ).fetchall()
            if not rows:
                return None
            if len(rows) > 1:
                raise RuntimeError(
                    f"duplicate active variants found for entry_id={entry_id}, source={source!r}"
                )
            return self._hydrate_rows(rows, conn=conn)[0]
        with get_conn() as local_conn:
            rows = local_conn.execute(
                """
                SELECT *
                FROM variants
                WHERE entry_id = ?
                  AND source = ?
                  AND trashed_at IS NULL
                ORDER BY variant_id
                """,
                (entry_id, source),
            ).fetchall()
            if not rows:
                return None
            if len(rows) > 1:
                raise RuntimeError(
                    f"duplicate active variants found for entry_id={entry_id}, source={source!r}"
                )
            return self._hydrate_rows(rows, conn=local_conn)[0]

    def list_by_entry(
        self,
        entry_id: int,
        include_trashed: bool = True,
        conn: sqlite3.Connection | None = None,
    ) -> list[VariantRecord]:
        params: list[Any] = [entry_id]
        where = ["entry_id = ?"]
        if not include_trashed:
            where.append("trashed_at IS NULL")
        if conn is not None:
            rows = conn.execute(
                f"""
                SELECT *
                FROM variants
                WHERE {' AND '.join(where)}
                ORDER BY variant_id
                """,
                params,
            ).fetchall()
            return self._hydrate_rows(rows, conn=conn)
        with get_conn() as local_conn:
            rows = local_conn.execute(
                f"""
                SELECT *
                FROM variants
                WHERE {' AND '.join(where)}
                ORDER BY variant_id
                """,
                params,
            ).fetchall()
            return self._hydrate_rows(rows, conn=local_conn)

    def list_by_entries(
        self,
        entry_ids: list[int],
        include_trashed: bool = True,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, list[VariantRecord]]:
        if not entry_ids:
            return {}
        placeholders = ", ".join("?" for _ in entry_ids)
        where = [f"entry_id IN ({placeholders})"]
        params: list[Any] = [*entry_ids]
        if not include_trashed:
            where.append("trashed_at IS NULL")
        if conn is not None:
            rows = conn.execute(
                f"""
                SELECT *
                FROM variants
                WHERE {' AND '.join(where)}
                ORDER BY variant_id
                """,
                params,
            ).fetchall()
            grouped: dict[int, list[VariantRecord]] = defaultdict(list)
            for variant in self._hydrate_rows(rows, conn=conn):
                grouped[int(variant["entry_id"])].append(variant)
            return grouped
        with get_conn() as local_conn:
            rows = local_conn.execute(
                f"""
                SELECT *
                FROM variants
                WHERE {' AND '.join(where)}
                ORDER BY variant_id
                """,
                params,
            ).fetchall()
            grouped: dict[int, list[VariantRecord]] = defaultdict(list)
            for variant in self._hydrate_rows(rows, conn=local_conn):
                grouped[int(variant["entry_id"])].append(variant)
            return grouped

    def list_by_entries_shallow(
        self,
        entry_ids: list[int],
        include_trashed: bool = True,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, list[dict[str, Any]]]:
        """Return variant rows grouped by entry_id WITHOUT hydrating translations/remarks."""
        if not entry_ids:
            return {}
        placeholders = ", ".join("?" for _ in entry_ids)
        where = [f"entry_id IN ({placeholders})"]
        params: list[Any] = [*entry_ids]
        if not include_trashed:
            where.append("trashed_at IS NULL")
        effective_conn = conn
        local_conn_ctx = None
        if effective_conn is None:
            local_conn_ctx = get_conn()
            effective_conn = local_conn_ctx.__enter__()
        try:
            rows = effective_conn.execute(
                f"""
                SELECT variant_id, entry_id, file_name, source,
                       orphaned_at, trashed_at, created_at, updated_at
                FROM variants
                WHERE {' AND '.join(where)}
                ORDER BY variant_id
                """,
                params,
            ).fetchall()
            grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                grouped[int(row["entry_id"])].append({
                    "variant_id": int(row["variant_id"]),
                    "entry_id": int(row["entry_id"]),
                    "file_name": row["file_name"],
                    "source": row["source"],
                    "orphaned_at": row["orphaned_at"],
                    "trashed_at": row["trashed_at"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                })
            return grouped
        finally:
            if local_conn_ctx is not None:
                local_conn_ctx.__exit__(None, None, None)

    def clear_orphaned_at(
        self,
        variant_id: int,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            conn.execute(
                """
                UPDATE variants
                SET orphaned_at = NULL,
                    updated_at = ?
                WHERE variant_id = ?
                """,
                (timestamp, variant_id),
            )
            return
        with get_conn() as local_conn:
            local_conn.execute(
                """
                UPDATE variants
                SET orphaned_at = NULL,
                    updated_at = ?
                WHERE variant_id = ?
                """,
                (timestamp, variant_id),
            )

    def set_orphaned_at(
        self,
        variant_id: int,
        orphaned_at: str | None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            conn.execute(
                """
                UPDATE variants
                SET orphaned_at = ?
                WHERE variant_id = ?
                """,
                (orphaned_at, variant_id),
            )
            return
        with get_conn() as local_conn:
            local_conn.execute(
                """
                UPDATE variants
                SET orphaned_at = ?
                WHERE variant_id = ?
                """,
                (orphaned_at, variant_id),
            )

    def trash_variant(
        self,
        variant_id: int,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            conn.execute(
                """
                UPDATE variants
                SET trashed_at = ?,
                    updated_at = ?
                WHERE variant_id = ?
                """,
                (timestamp, timestamp, variant_id),
            )
            return
        with get_conn() as local_conn:
            self.trash_variant(variant_id, timestamp, conn=local_conn)

    def set_pivot_changed(
        self,
        variant_id: int,
        scope_type: str,
        scope_value: str,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            conn.execute(
                """
                UPDATE variants
                SET pivot_status = 'changed',
                    pivot_changed_by_scope_type = ?,
                    pivot_changed_by_scope_value = ?,
                    pivot_changed_at = ?,
                    pivot_status_updated_at = ?
                WHERE variant_id = ?
                """,
                (scope_type, scope_value, timestamp, timestamp, variant_id),
            )
            return
        with get_conn() as local_conn:
            self.set_pivot_changed(variant_id, scope_type, scope_value, timestamp, conn=local_conn)

    def bulk_create_variants(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> list[int]:
        if not rows:
            return []
        cursor = conn.execute("SELECT MAX(variant_id) AS max_id FROM variants")
        max_before = cursor.fetchone()["max_id"] or 0
        conn.executemany(
            """
            INSERT INTO variants(
                entry_id, file_name, source, orphaned_at,
                pivot_status, pivot_status_updated_at, created_at, updated_at
            )
            VALUES (?, ?, ?, NULL, 'init', ?, ?, ?)
            """,
            [(entry_id, file_name, source, ts, ts, ts) for entry_id, file_name, source, ts in rows],
        )
        new_rows = conn.execute(
            "SELECT variant_id FROM variants WHERE variant_id > ? ORDER BY variant_id",
            (max_before,),
        ).fetchall()
        return [int(r["variant_id"]) for r in new_rows]

    def bulk_write_translations(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO variant_translations(variant_id, lang, target_text, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )

    def bulk_upsert_translations(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO variant_translations(variant_id, lang, target_text, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(variant_id, lang) DO UPDATE SET
                target_text = excluded.target_text,
                updated_at = excluded.updated_at
            """,
            rows,
        )

    def bulk_write_remarks(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO variant_remarks(variant_id, remark_key, remark_value, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )

    def bulk_upsert_remarks(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        if not rows:
            return
        conn.executemany(
            """
            INSERT INTO variant_remarks(variant_id, remark_key, remark_value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(variant_id, remark_key) DO UPDATE SET
                remark_value = excluded.remark_value,
                updated_at = excluded.updated_at
            """,
            rows,
        )

    def bulk_update_variant_files(
        self,
        rows: list[tuple[int, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        if not rows:
            return
        conn.executemany(
            """
            UPDATE variants
            SET file_name = ?,
                updated_at = ?
            WHERE variant_id = ?
            """,
            [(file_name, updated_at, variant_id) for variant_id, file_name, updated_at in rows],
        )

    def bulk_set_pivot_changed(
        self,
        rows: list[tuple[int, str, str, str]],
        *,
        conn: sqlite3.Connection,
    ) -> None:
        if not rows:
            return
        conn.executemany(
            """
            UPDATE variants
            SET pivot_status = 'changed',
                pivot_changed_by_scope_type = ?,
                pivot_changed_by_scope_value = ?,
                pivot_changed_at = ?,
                pivot_status_updated_at = ?
            WHERE variant_id = ?
            """,
            [
                (scope_type, scope_value, timestamp, timestamp, variant_id)
                for variant_id, scope_type, scope_value, timestamp in rows
            ],
        )

    def set_pivot_reviewed(
        self,
        variant_id: int,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            conn.execute(
                """
                UPDATE variants
                SET pivot_status = 'reviewed',
                    pivot_changed_by_scope_type = NULL,
                    pivot_changed_by_scope_value = NULL,
                    pivot_reviewed_at = ?,
                    pivot_status_updated_at = ?
                WHERE variant_id = ?
                """,
                (timestamp, timestamp, variant_id),
            )
            return
        with get_conn() as local_conn:
            self.set_pivot_reviewed(variant_id, timestamp, conn=local_conn)

    def _hydrate_rows(
        self,
        rows: list[dict[str, Any]],
        conn: sqlite3.Connection | None = None,
    ) -> list[VariantRecord]:
        if not rows:
            return []
        variant_ids = sorted({int(row["variant_id"]) for row in rows})
        if conn is not None:
            translation_rows, remark_rows = self._select_content_rows_by_variant_ids(variant_ids, conn=conn)
        else:
            with get_conn() as local_conn:
                translation_rows, remark_rows = self._select_content_rows_by_variant_ids(
                    variant_ids,
                    conn=local_conn,
                )
        translations_by_id: dict[int, dict[str, str]] = defaultdict(dict)
        for row in translation_rows:
            translations_by_id[int(row["variant_id"])][row["lang"]] = normalize_content_value(row["target_text"])
        remarks_by_id: dict[int, dict[str, str]] = defaultdict(dict)
        for row in remark_rows:
            remarks_by_id[int(row["variant_id"])][row["remark_key"]] = normalize_non_content_value(
                row["remark_value"]
            )
        return [
            {
                "variant_id": int(row["variant_id"]),
                "entry_id": int(row["entry_id"]),
                "file_name": normalize_non_content_value(row["file_name"]),
                "source": normalize_non_content_value(row["source"]),
                "translations": translations_by_id.get(int(row["variant_id"]), {}),
                "remarks": remarks_by_id.get(int(row["variant_id"]), {}),
                "orphaned_at": row["orphaned_at"],
                "trashed_at": row["trashed_at"],
                "pivot_status": str(row["pivot_status"]),
                "pivot_changed_by_scope_type": (
                    str(row["pivot_changed_by_scope_type"])
                    if row["pivot_changed_by_scope_type"] is not None
                    else None
                ),
                "pivot_changed_by_scope_value": (
                    str(row["pivot_changed_by_scope_value"])
                    if row["pivot_changed_by_scope_value"] is not None
                    else None
                ),
                "pivot_changed_at": row["pivot_changed_at"],
                "pivot_reviewed_at": row["pivot_reviewed_at"],
                "pivot_status_updated_at": row["pivot_status_updated_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def _select_rows_by_variant_ids(
        self,
        variant_ids: list[int],
        *,
        conn: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for chunk in iter_sql_chunks(variant_ids, conn):
            placeholders = ", ".join("?" for _ in chunk)
            rows.extend(
                conn.execute(
                    f"""
                    SELECT *
                    FROM variants
                    WHERE variant_id IN ({placeholders})
                    ORDER BY variant_id
                    """,
                    chunk,
                ).fetchall()
            )
        return rows

    def _select_content_rows_by_variant_ids(
        self,
        variant_ids: list[int],
        *,
        conn: sqlite3.Connection,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        translation_rows: list[dict[str, Any]] = []
        remark_rows: list[dict[str, Any]] = []
        for chunk in iter_sql_chunks(variant_ids, conn):
            placeholders = ", ".join("?" for _ in chunk)
            translation_rows.extend(
                conn.execute(
                    f"""
                    SELECT variant_id, lang, target_text
                    FROM variant_translations
                    WHERE variant_id IN ({placeholders})
                    ORDER BY lang
                    """,
                    chunk,
                ).fetchall()
            )
            remark_rows.extend(
                conn.execute(
                    f"""
                    SELECT variant_id, remark_key, remark_value
                    FROM variant_remarks
                    WHERE variant_id IN ({placeholders})
                    ORDER BY remark_key
                    """,
                    chunk,
                ).fetchall()
            )
        return translation_rows, remark_rows

    def hydrate_variant_rows(
        self,
        rows: list[dict[str, Any]],
        conn: sqlite3.Connection | None = None,
    ) -> list[VariantRecord]:
        required_columns = {
            "variant_id",
            "entry_id",
            "file_name",
            "source",
            "orphaned_at",
            "trashed_at",
            "pivot_status",
            "pivot_changed_by_scope_type",
            "pivot_changed_by_scope_value",
            "pivot_changed_at",
            "pivot_reviewed_at",
            "pivot_status_updated_at",
            "created_at",
            "updated_at",
        }
        if rows and not required_columns.issubset(rows[0].keys()):
            variant_ids: list[int] = []
            seen: set[int] = set()
            for row in rows:
                variant_id = int(row["variant_id"])
                if variant_id in seen:
                    continue
                seen.add(variant_id)
                variant_ids.append(variant_id)
            if conn is not None:
                canonical_rows = self._select_rows_by_variant_ids(variant_ids, conn=conn)
            else:
                with get_conn() as local_conn:
                    canonical_rows = self._select_rows_by_variant_ids(variant_ids, conn=local_conn)
            rows_by_id = {
                int(row["variant_id"]): row
                for row in canonical_rows
            }
            if len(rows_by_id) != len(variant_ids):
                missing_ids = [variant_id for variant_id in variant_ids if variant_id not in rows_by_id]
                raise KeyError(f"variant rows not found: {missing_ids}")
            rows = [rows_by_id[int(row["variant_id"])] for row in rows]
        return self._hydrate_rows(rows, conn=conn)
