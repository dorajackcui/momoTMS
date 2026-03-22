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
from app.services.shared.utils import now_iso
from app.services.variant.normalization import require_non_content_value
from app.services.variant.records import VariantContent, VariantRecord


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
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (entry_id, file_name, source, timestamp, timestamp, timestamp),
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
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (entry_id, file_name, source, timestamp, timestamp, timestamp),
            )
        return int(cur.lastrowid)

    def update(
        self,
        variant_id: int,
        file_name: str,
        source: str,
        timestamp: str,
        restore_if_trashed: bool = False,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            if restore_if_trashed:
                conn.execute(
                    """
                    UPDATE variants
                    SET file_name = ?,
                        source = ?,
                        trashed_at = NULL,
                        trash_until = NULL,
                        restored_at = ?,
                        updated_at = ?
                    WHERE variant_id = ?
                    """,
                    (file_name, source, timestamp, timestamp, variant_id),
                )
            else:
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
                restore_if_trashed=restore_if_trashed,
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
        trash_until: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if conn is not None:
            conn.execute(
                """
                UPDATE variants
                SET trashed_at = ?,
                    trash_until = ?,
                    updated_at = ?
                WHERE variant_id = ?
                """,
                (timestamp, trash_until, timestamp, variant_id),
            )
            return
        with get_conn() as local_conn:
            self.trash_variant(variant_id, timestamp, trash_until, conn=local_conn)

    def restore_variant(
        self,
        variant_id: int,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> bool:
        if conn is not None:
            cur = conn.execute(
                """
                UPDATE variants
                SET trashed_at = NULL,
                    trash_until = NULL,
                    restored_at = ?,
                    updated_at = ?
                WHERE variant_id = ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM variants active
                      WHERE active.entry_id = variants.entry_id
                        AND active.source = variants.source
                        AND active.trashed_at IS NULL
                        AND active.variant_id != variants.variant_id
                  )
                """,
                (timestamp, timestamp, variant_id),
            )
            return cur.rowcount > 0
        with get_conn() as local_conn:
            return self.restore_variant(variant_id, timestamp, conn=local_conn)

    def _hydrate_rows(
        self,
        rows: list[dict[str, Any]],
        conn: sqlite3.Connection | None = None,
    ) -> list[VariantRecord]:
        if not rows:
            return []
        variant_ids = [int(row["variant_id"]) for row in rows]
        placeholders = ", ".join("?" for _ in variant_ids)
        if conn is not None:
            translation_rows = conn.execute(
                f"""
                SELECT variant_id, lang, target_text
                FROM variant_translations
                WHERE variant_id IN ({placeholders})
                ORDER BY lang
                """,
                variant_ids,
            ).fetchall()
            remark_rows = conn.execute(
                f"""
                SELECT variant_id, remark_key, remark_value
                FROM variant_remarks
                WHERE variant_id IN ({placeholders})
                ORDER BY remark_key
                """,
                variant_ids,
            ).fetchall()
        else:
            with get_conn() as local_conn:
                translation_rows = local_conn.execute(
                    f"""
                    SELECT variant_id, lang, target_text
                    FROM variant_translations
                    WHERE variant_id IN ({placeholders})
                    ORDER BY lang
                    """,
                    variant_ids,
                ).fetchall()
                remark_rows = local_conn.execute(
                    f"""
                    SELECT variant_id, remark_key, remark_value
                    FROM variant_remarks
                    WHERE variant_id IN ({placeholders})
                    ORDER BY remark_key
                    """,
                    variant_ids,
                ).fetchall()
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
                "trash_until": row["trash_until"],
                "restored_at": row["restored_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def hydrate_variant_rows(
        self,
        rows: list[dict[str, Any]],
        conn: sqlite3.Connection | None = None,
    ) -> list[VariantRecord]:
        return self._hydrate_rows(rows, conn=conn)


class VariantCommandRepository:
    def __init__(self, store: _VariantStore | None = None) -> None:
        self._store = store or _VariantStore()

    def create(
        self,
        entry_id: int,
        file_name: str,
        source: str,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        return self._store.create(entry_id, file_name, source, timestamp, conn=conn)

    def update(
        self,
        variant_id: int,
        file_name: str,
        source: str,
        timestamp: str,
        restore_if_trashed: bool = False,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self._store.update(
            variant_id,
            file_name,
            source,
            timestamp,
            restore_if_trashed=restore_if_trashed,
            conn=conn,
        )

    def overwrite_translations(
        self,
        variant_id: int,
        translations: dict[str, str],
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self._store.overwrite_translations(variant_id, translations, timestamp, conn=conn)

    def overwrite_remarks(
        self,
        variant_id: int,
        remarks: dict[str, str],
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self._store.overwrite_remarks(variant_id, remarks, timestamp, conn=conn)

    def clear_orphaned_at(
        self,
        variant_id: int,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self._store.clear_orphaned_at(variant_id, timestamp, conn=conn)

    def set_orphaned_at(
        self,
        variant_id: int,
        orphaned_at: str | None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self._store.set_orphaned_at(variant_id, orphaned_at, conn=conn)

    def trash_variant(
        self,
        variant_id: int,
        timestamp: str,
        trash_until: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self._store.trash_variant(variant_id, timestamp, trash_until, conn=conn)

    def restore_variant(
        self,
        variant_id: int,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> bool:
        return self._store.restore_variant(variant_id, timestamp, conn=conn)


class VariantQueryRepository:
    def __init__(self, store: _VariantStore | None = None) -> None:
        self._store = store or _VariantStore()

    def get(self, variant_id: int, conn: sqlite3.Connection | None = None) -> VariantRecord | None:
        return self._store.get(variant_id, conn=conn)

    def get_active_by_entry_and_source(
        self,
        entry_id: int,
        source: str,
        conn: sqlite3.Connection | None = None,
    ) -> VariantRecord | None:
        return self._store.get_active_by_entry_and_source(entry_id, source, conn=conn)

    def list_by_entry(
        self,
        entry_id: int,
        include_trashed: bool = True,
        conn: sqlite3.Connection | None = None,
    ) -> list[VariantRecord]:
        return self._store.list_by_entry(entry_id, include_trashed=include_trashed, conn=conn)

    def list_by_entries(
        self,
        entry_ids: list[int],
        include_trashed: bool = True,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, list[VariantRecord]]:
        return self._store.list_by_entries(entry_ids, include_trashed=include_trashed, conn=conn)

    def hydrate_variant_rows(
        self,
        rows: list[dict[str, Any]],
        conn: sqlite3.Connection | None = None,
    ) -> list[VariantRecord]:
        return self._store.hydrate_variant_rows(rows, conn=conn)


class VariantCatalogService:
    def __init__(
        self,
        variant_commands: VariantCommandRepository | None = None,
        variant_queries: VariantQueryRepository | None = None,
    ) -> None:
        self._commands = variant_commands or VariantCommandRepository()
        self._queries = variant_queries or VariantQueryRepository()

    def build_content(
        self,
        file_name: str | None,
        source: str,
        translations: dict[str, str | None],
        remarks: dict[str, str | None],
    ) -> VariantContent:
        return {
            "file_name": normalize_non_content_value(file_name),
            "source": require_non_content_value("source", source),
            "translations": normalize_content_map(translations),
            "remarks": normalize_non_content_map(remarks),
        }

    def create_variant(
        self,
        entry_id: int,
        content: VariantContent,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        timestamp = now_iso()
        variant_id = self._commands.create(
            entry_id,
            content["file_name"],
            content["source"],
            timestamp,
            conn=conn,
        )
        self._commands.overwrite_translations(variant_id, content["translations"], timestamp, conn=conn)
        self._commands.overwrite_remarks(variant_id, content["remarks"], timestamp, conn=conn)
        return variant_id

    def update_variant(
        self,
        variant_id: int,
        content: VariantContent,
        restore_if_trashed: bool = False,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        timestamp = now_iso()
        self._commands.update(
            variant_id,
            content["file_name"],
            content["source"],
            timestamp,
            restore_if_trashed=restore_if_trashed,
            conn=conn,
        )
        self._commands.overwrite_translations(variant_id, content["translations"], timestamp, conn=conn)
        self._commands.overwrite_remarks(variant_id, content["remarks"], timestamp, conn=conn)

    def get_variant(self, variant_id: int, conn: sqlite3.Connection | None = None) -> VariantRecord:
        variant = self._queries.get(variant_id, conn=conn)
        if variant is None:
            raise KeyError(f"variant not found: {variant_id}")
        return variant

    def find_variant_by_source(
        self,
        entry_id: int,
        source: str,
        include_trashed: bool = False,
        conn: sqlite3.Connection | None = None,
    ) -> VariantRecord | None:
        normalized_source = require_non_content_value("source", source)
        if not include_trashed:
            return self._queries.get_active_by_entry_and_source(entry_id, normalized_source, conn=conn)
        matches = [
            variant
            for variant in self.list_variants(entry_id, include_trashed=True, conn=conn)
            if variant["source"] == normalized_source
        ]
        if not matches:
            return None
        active_matches = [variant for variant in matches if variant["trashed_at"] is None]
        if len(active_matches) > 1:
            raise RuntimeError(
                f"duplicate active variants found for entry_id={entry_id}, source={normalized_source!r}"
            )
        if active_matches:
            return active_matches[0]
        return matches[-1]

    def list_variants(
        self,
        entry_id: int,
        include_trashed: bool = True,
        conn: sqlite3.Connection | None = None,
    ) -> list[VariantRecord]:
        return self._queries.list_by_entry(entry_id, include_trashed=include_trashed, conn=conn)

    def list_variants_for_entries(
        self,
        entry_ids: list[int],
        include_trashed: bool = True,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, list[VariantRecord]]:
        return self._queries.list_by_entries(entry_ids, include_trashed=include_trashed, conn=conn)
