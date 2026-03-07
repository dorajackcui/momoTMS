from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.db import get_conn
from app.services.shared.io import (
    normalize_content_value,
    normalize_non_content_value,
)
from app.services.variant.records import (
    BindingRecord,
    EntryRecord,
    RetainedVariantRecord,
    ScopeEntryRecord,
    VariantRecord,
)


class EntryRepository:
    def get_by_business_key(self, project_id: int, business_key: str) -> EntryRecord | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM entries
                WHERE project_id = ? AND business_key = ?
                LIMIT 1
                """,
                (project_id, business_key),
            ).fetchone()
        if not row:
            return None
        return self._hydrate_rows([row])[0]

    def get_by_id(self, entry_id: int) -> EntryRecord | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM entries WHERE entry_id = ? LIMIT 1",
                (entry_id,),
            ).fetchone()
        if not row:
            return None
        return self._hydrate_rows([row])[0]

    def create(self, project_id: int, business_key: str, timestamp: str) -> EntryRecord:
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO entries(project_id, business_key, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (project_id, business_key, timestamp, timestamp),
            )
            row = conn.execute(
                "SELECT * FROM entries WHERE entry_id = ?",
                (int(cur.lastrowid),),
            ).fetchone()
        return self._hydrate_rows([row])[0]

    def insert_many_ignore(self, project_id: int, business_keys: list[str], timestamp: str) -> None:
        if not business_keys:
            return
        with get_conn() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO entries(project_id, business_key, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                [(project_id, key, timestamp, timestamp) for key in business_keys],
            )

    def get_by_keys(self, project_id: int, business_keys: list[str]) -> dict[str, EntryRecord]:
        if not business_keys:
            return {}
        placeholders = ", ".join("?" for _ in business_keys)
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM entries
                WHERE project_id = ? AND business_key IN ({placeholders})
                """,
                [project_id, *business_keys],
            ).fetchall()
        hydrated = self._hydrate_rows(rows)
        return {entry["business_key"]: entry for entry in hydrated}

    def list(self, project_id: int, search: str | None = None) -> list[EntryRecord]:
        params: list[Any] = [project_id]
        where = ["e.project_id = ?"]
        if search:
            needle = f"%{normalize_non_content_value(search)}%"
            where.append(
                """
                (
                    e.business_key LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM variants v
                        WHERE v.entry_id = e.entry_id
                          AND (COALESCE(v.source, '') LIKE ? OR COALESCE(v.file_name, '') LIKE ?)
                    )
                )
                """
            )
            params.extend([needle, needle, needle])
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT e.*
                FROM entries e
                WHERE {' AND '.join(where)}
                ORDER BY e.business_key
                """,
                params,
            ).fetchall()
        return self._hydrate_rows(rows)

    def _hydrate_rows(self, rows: list[dict[str, Any]]) -> list[EntryRecord]:
        return [
            {
                "entry_id": int(row["entry_id"]),
                "project_id": int(row["project_id"]),
                "business_key": normalize_non_content_value(row["business_key"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]


class VariantRepository:
    def create(self, entry_id: int, file_name: str, source: str, timestamp: str) -> int:
        with get_conn() as conn:
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

    def update(
        self,
        variant_id: int,
        file_name: str,
        source: str,
        timestamp: str,
        restore_if_trashed: bool = False,
    ) -> None:
        with get_conn() as conn:
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

    def replace_translations(self, variant_id: int, translations: dict[str, str], timestamp: str) -> None:
        with get_conn() as conn:
            for lang, target_text in translations.items():
                conn.execute(
                    """
                    INSERT INTO variant_translations(variant_id, lang, target_text, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(variant_id, lang)
                    DO UPDATE SET
                        target_text = excluded.target_text,
                        updated_at = excluded.updated_at
                    """,
                    (variant_id, lang, target_text, timestamp),
                )

    def replace_remarks(self, variant_id: int, remarks: dict[str, str], timestamp: str) -> None:
        with get_conn() as conn:
            for remark_key, remark_value in remarks.items():
                conn.execute(
                    """
                    INSERT INTO variant_remarks(variant_id, remark_key, remark_value, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(variant_id, remark_key)
                    DO UPDATE SET
                        remark_value = excluded.remark_value,
                        updated_at = excluded.updated_at
                    """,
                    (variant_id, remark_key, remark_value, timestamp),
                )

    def get(self, variant_id: int) -> VariantRecord | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM variants WHERE variant_id = ?",
                (variant_id,),
            ).fetchone()
        if not row:
            return None
        return self._hydrate_rows([row])[0]

    def list_by_entry(self, entry_id: int, include_trashed: bool = True) -> list[VariantRecord]:
        params: list[Any] = [entry_id]
        where = ["entry_id = ?"]
        if not include_trashed:
            where.append("trashed_at IS NULL")
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM variants
                WHERE {' AND '.join(where)}
                ORDER BY variant_id
                """,
                params,
            ).fetchall()
        return self._hydrate_rows(rows)

    def list_by_entries(
        self,
        entry_ids: list[int],
        include_trashed: bool = True,
    ) -> dict[int, list[VariantRecord]]:
        if not entry_ids:
            return {}
        placeholders = ", ".join("?" for _ in entry_ids)
        where = [f"entry_id IN ({placeholders})"]
        params: list[Any] = [*entry_ids]
        if not include_trashed:
            where.append("trashed_at IS NULL")
        with get_conn() as conn:
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
        for variant in self._hydrate_rows(rows):
            grouped[int(variant["entry_id"])].append(variant)
        return grouped

    def clear_orphaned_at(self, variant_id: int, timestamp: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE variants
                SET orphaned_at = NULL,
                    updated_at = ?
                WHERE variant_id = ?
                """,
                (timestamp, variant_id),
            )

    def set_orphaned_at(self, variant_id: int, orphaned_at: str | None) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE variants
                SET orphaned_at = ?
                WHERE variant_id = ?
                """,
                (orphaned_at, variant_id),
            )

    def counts_for_business_keys(self, project_id: int, business_keys: list[str]) -> dict[str, dict[str, int]]:
        if not business_keys:
            return {}
        placeholders = ", ".join("?" for _ in business_keys)
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT e.business_key,
                       e.entry_id,
                       SUM(CASE WHEN v.trashed_at IS NULL THEN 1 ELSE 0 END) AS active_variant_count,
                       SUM(CASE WHEN v.trashed_at IS NOT NULL THEN 1 ELSE 0 END) AS trashed_variant_count,
                       COUNT(v.variant_id) AS variant_count
                FROM entries e
                LEFT JOIN variants v ON v.entry_id = e.entry_id
                WHERE e.project_id = ? AND e.business_key IN ({placeholders})
                GROUP BY e.entry_id, e.business_key
                """,
                [project_id, *business_keys],
            ).fetchall()
        return {
            row["business_key"]: {
                "entry_id": int(row["entry_id"]),
                "active_variant_count": int(row["active_variant_count"] or 0),
                "trashed_variant_count": int(row["trashed_variant_count"] or 0),
                "variant_count": int(row["variant_count"] or 0),
            }
            for row in rows
        }

    def trash_entry_variants(
        self,
        project_id: int,
        business_key: str,
        timestamp: str,
        trash_until: str,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE variants
                SET trashed_at = ?,
                    trash_until = ?,
                    updated_at = ?
                WHERE entry_id = (
                    SELECT entry_id FROM entries WHERE project_id = ? AND business_key = ?
                )
                  AND trashed_at IS NULL
                """,
                (timestamp, trash_until, timestamp, project_id, business_key),
            )

    def restore_entry_variants(self, project_id: int, business_key: str, timestamp: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE variants
                SET trashed_at = NULL,
                    trash_until = NULL,
                    restored_at = ?,
                    updated_at = ?
                WHERE entry_id = (
                    SELECT entry_id FROM entries WHERE project_id = ? AND business_key = ?
                )
                  AND trashed_at IS NOT NULL
                """,
                (timestamp, timestamp, project_id, business_key),
            )

    def count_trashed_entries(self, project_id: int) -> int:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(DISTINCT e.entry_id) AS count
                FROM entries e
                JOIN variants v ON v.entry_id = e.entry_id
                WHERE e.project_id = ? AND v.trashed_at IS NOT NULL
                """,
                (project_id,),
            ).fetchone()
        return int(row["count"] or 0)

    def _hydrate_rows(self, rows: list[dict[str, Any]]) -> list[VariantRecord]:
        if not rows:
            return []
        variant_ids = [int(row["variant_id"]) for row in rows]
        placeholders = ", ".join("?" for _ in variant_ids)
        with get_conn() as conn:
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


class ScopeBindingRepository:
    def upsert(
        self,
        entry_id: int,
        scope_type: str,
        scope_value: str,
        variant_id: int,
        timestamp: str,
    ) -> int | None:
        with get_conn() as conn:
            previous = conn.execute(
                """
                SELECT variant_id
                FROM scope_bindings
                WHERE scope_type = ? AND scope_value = ? AND entry_id = ?
                LIMIT 1
                """,
                (scope_type, scope_value, entry_id),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO scope_bindings(
                    scope_type,
                    scope_value,
                    entry_id,
                    variant_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope_type, scope_value, entry_id)
                DO UPDATE SET
                    variant_id = excluded.variant_id,
                    updated_at = excluded.updated_at
                """,
                (scope_type, scope_value, entry_id, variant_id, timestamp, timestamp),
            )
        if not previous:
            return None
        return int(previous["variant_id"])

    def get(self, entry_id: int, scope_type: str, scope_value: str) -> BindingRecord | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM scope_bindings
                WHERE scope_type = ? AND scope_value = ? AND entry_id = ?
                LIMIT 1
                """,
                (scope_type, scope_value, entry_id),
            ).fetchone()
        if not row:
            return None
        return self._hydrate_rows([row])[0]

    def get_for_entries(self, entry_ids: list[int], scope_type: str, scope_value: str) -> dict[int, BindingRecord]:
        if not entry_ids:
            return {}
        placeholders = ", ".join("?" for _ in entry_ids)
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM scope_bindings
                WHERE scope_type = ?
                  AND scope_value = ?
                  AND entry_id IN ({placeholders})
                """,
                [scope_type, scope_value, *entry_ids],
            ).fetchall()
        return {int(row["entry_id"]): row for row in self._hydrate_rows(rows)}

    def list_for_entry(self, entry_id: int) -> list[BindingRecord]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM scope_bindings
                WHERE entry_id = ?
                ORDER BY scope_type, scope_value
                """,
                (entry_id,),
            ).fetchall()
        return self._hydrate_rows(rows)

    def list_scope_entries(
        self,
        project_id: int,
        scope_type: str,
        scope_value: str,
        variant_repo: VariantRepository,
    ) -> list[ScopeEntryRecord]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT e.entry_id, e.project_id, e.business_key, e.created_at AS entry_created_at, e.updated_at AS entry_updated_at,
                       v.variant_id, v.file_name, v.source, v.orphaned_at, v.trashed_at, v.trash_until, v.restored_at, v.created_at AS variant_created_at, v.updated_at AS variant_updated_at,
                       b.scope_type, b.scope_value
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
        return self._hydrate_bound_rows(rows, variant_repo)

    def count_scope(self, project_id: int, scope_type: str, scope_value: str) -> int:
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

    def clear_scope(self, project_id: int, scope_type: str, scope_value: str) -> list[BindingRecord]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM scope_bindings
                WHERE scope_type = ? AND scope_value = ?
                  AND entry_id IN (SELECT entry_id FROM entries WHERE project_id = ?)
                """,
                (scope_type, scope_value, project_id),
            ).fetchall()
            conn.execute(
                """
                DELETE FROM scope_bindings
                WHERE scope_type = ? AND scope_value = ?
                  AND entry_id IN (SELECT entry_id FROM entries WHERE project_id = ?)
                """,
                (scope_type, scope_value, project_id),
            )
        return self._hydrate_rows(rows)

    def remove_scope_bindings(
        self,
        project_id: int,
        scope_type: str,
        scope_values: list[str],
    ) -> list[BindingRecord]:
        if not scope_values:
            return []
        placeholders = ", ".join("?" for _ in scope_values)
        params = [scope_type, *scope_values, project_id]
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM scope_bindings
                WHERE scope_type = ?
                  AND scope_value IN ({placeholders})
                  AND entry_id IN (SELECT entry_id FROM entries WHERE project_id = ?)
                """,
                params,
            ).fetchall()
            conn.execute(
                f"""
                DELETE FROM scope_bindings
                WHERE scope_type = ?
                  AND scope_value IN ({placeholders})
                  AND entry_id IN (SELECT entry_id FROM entries WHERE project_id = ?)
                """,
                params,
            )
        return self._hydrate_rows(rows)

    def count_for_variant(self, variant_id: int) -> int:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM scope_bindings
                WHERE variant_id = ?
                """,
                (variant_id,),
            ).fetchone()
        return int(row["count"] or 0)

    def binding_counts_for_entry(self, entry_id: int) -> dict[int, int]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT variant_id, COUNT(*) AS count
                FROM scope_bindings
                WHERE entry_id = ?
                GROUP BY variant_id
                """,
                (entry_id,),
            ).fetchall()
        return {int(row["variant_id"]): int(row["count"] or 0) for row in rows}

    def _hydrate_rows(self, rows: list[dict[str, Any]]) -> list[BindingRecord]:
        return [
            {
                "scope_type": row["scope_type"],
                "scope_value": row["scope_value"],
                "entry_id": int(row["entry_id"]),
                "variant_id": int(row["variant_id"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def _hydrate_bound_rows(
        self,
        rows: list[dict[str, Any]],
        variant_repo: VariantRepository,
    ) -> list[ScopeEntryRecord]:
        if not rows:
            return []
        variant_rows = [
            {
                "variant_id": row["variant_id"],
                "entry_id": row["entry_id"],
                "file_name": row["file_name"],
                "source": row["source"],
                "orphaned_at": row["orphaned_at"],
                "trashed_at": row["trashed_at"],
                "trash_until": row["trash_until"],
                "restored_at": row["restored_at"],
                "created_at": row["variant_created_at"],
                "updated_at": row["variant_updated_at"],
            }
            for row in rows
        ]
        variants_by_id = {variant["variant_id"]: variant for variant in variant_repo._hydrate_rows(variant_rows)}
        hydrated: list[ScopeEntryRecord] = []
        for row in rows:
            hydrated.append(
                {
                    "entry_id": int(row["entry_id"]),
                    "project_id": int(row["project_id"]),
                    "business_key": normalize_non_content_value(row["business_key"]),
                    "variant": variants_by_id[int(row["variant_id"])],
                    "scope_type": row["scope_type"],
                    "scope_value": row["scope_value"],
                    "created_at": row["entry_created_at"],
                    "updated_at": row["entry_updated_at"],
                }
            )
        return hydrated


class RetainedVariantRepository:
    def list_for_entry(self, entry_id: int) -> list[RetainedVariantRecord]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM retained_variants
                WHERE entry_id = ?
                ORDER BY retained_at DESC, variant_id DESC
                """,
                (entry_id,),
            ).fetchall()
        return self._hydrate_rows(rows)

    def upsert(
        self,
        variant_id: int,
        entry_id: int,
        last_active_scope_type: str,
        last_active_scope_value: str,
        timestamp: str,
    ) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO retained_variants(
                    variant_id,
                    entry_id,
                    last_active_scope_type,
                    last_active_scope_value,
                    retained_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(variant_id)
                DO UPDATE SET
                    last_active_scope_type = excluded.last_active_scope_type,
                    last_active_scope_value = excluded.last_active_scope_value,
                    updated_at = excluded.updated_at
                """,
                (
                    variant_id,
                    entry_id,
                    last_active_scope_type,
                    last_active_scope_value,
                    timestamp,
                    timestamp,
                ),
            )

    def delete_by_variant(self, variant_id: int) -> None:
        with get_conn() as conn:
            conn.execute(
                "DELETE FROM retained_variants WHERE variant_id = ?",
                (variant_id,),
            )

    def delete_by_entry(self, entry_id: int) -> None:
        with get_conn() as conn:
            conn.execute(
                "DELETE FROM retained_variants WHERE entry_id = ?",
                (entry_id,),
            )

    def exists(self, variant_id: int) -> bool:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM retained_variants
                WHERE variant_id = ?
                LIMIT 1
                """,
                (variant_id,),
            ).fetchone()
        return row is not None

    def retained_variant_ids_for_entry(self, entry_id: int) -> set[int]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT variant_id
                FROM retained_variants
                WHERE entry_id = ?
                """,
                (entry_id,),
            ).fetchall()
        return {int(row["variant_id"]) for row in rows}

    def list_entries(self, project_id: int, variant_repo: VariantRepository) -> list[ScopeEntryRecord]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT e.entry_id, e.project_id, e.business_key, e.created_at AS entry_created_at, e.updated_at AS entry_updated_at,
                       v.variant_id, v.file_name, v.source, v.orphaned_at, v.trashed_at, v.trash_until, v.restored_at, v.created_at AS variant_created_at, v.updated_at AS variant_updated_at,
                       'retained' AS scope_type, 'retained' AS scope_value,
                       r.last_active_scope_type, r.last_active_scope_value, r.retained_at, r.updated_at AS retained_updated_at
                FROM retained_variants r
                JOIN entries e ON e.entry_id = r.entry_id
                JOIN variants v ON v.variant_id = r.variant_id
                WHERE e.project_id = ?
                  AND v.trashed_at IS NULL
                ORDER BY e.business_key, r.retained_at DESC
                """,
                (project_id,),
            ).fetchall()
        hydrated = ScopeBindingRepository()._hydrate_bound_rows(rows, variant_repo)
        for item, row in zip(hydrated, rows, strict=True):
            item["scope_type"] = "retained"
            item["scope_value"] = "retained"
            item["last_active_scope_type"] = row["last_active_scope_type"]
            item["last_active_scope_value"] = row["last_active_scope_value"]
            item["retained_at"] = row["retained_at"]
        return hydrated

    def _hydrate_rows(self, rows: list[dict[str, Any]]) -> list[RetainedVariantRecord]:
        return [
            {
                "variant_id": int(row["variant_id"]),
                "entry_id": int(row["entry_id"]),
                "membership_type": "retained",
                "membership_value": "retained",
                "last_active_scope_type": row["last_active_scope_type"],
                "last_active_scope_value": row["last_active_scope_value"],
                "retained_at": row["retained_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
