from __future__ import annotations

from collections import defaultdict
import sqlite3
from typing import Any

from app.db import get_conn
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.utils import now_iso
from app.services.variant.records import BindingRecord
from app.services.variant.repositories import VariantCommandRepository, VariantQueryRepository


def _scope_tuple(scope_ref: Any) -> tuple[str, str]:
    if hasattr(scope_ref, "as_tuple"):
        return scope_ref.as_tuple()
    if isinstance(scope_ref, tuple) and len(scope_ref) == 2:
        return str(scope_ref[0]), str(scope_ref[1])
    if isinstance(scope_ref, str) and "/" in scope_ref:
        scope_type, scope_value = scope_ref.split("/", 1)
        return scope_type, scope_value
    raise TypeError(f"unsupported scope reference: {scope_ref!r}")


class _ScopeBindingStore:
    def upsert(
        self,
        entry_id: int,
        scope_type: str,
        scope_value: str,
        variant_id: int,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> int | None:
        if conn is not None:
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
        with get_conn() as local_conn:
            previous = local_conn.execute(
                """
                SELECT variant_id
                FROM scope_bindings
                WHERE scope_type = ? AND scope_value = ? AND entry_id = ?
                LIMIT 1
                """,
                (scope_type, scope_value, entry_id),
            ).fetchone()
            local_conn.execute(
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

    def get(
        self,
        entry_id: int,
        scope_type: str,
        scope_value: str,
        conn: sqlite3.Connection | None = None,
    ) -> BindingRecord | None:
        if conn is not None:
            row = conn.execute(
                """
                SELECT *
                FROM scope_bindings
                WHERE scope_type = ? AND scope_value = ? AND entry_id = ?
                LIMIT 1
                """,
                (scope_type, scope_value, entry_id),
            ).fetchone()
        else:
            with get_conn() as local_conn:
                row = local_conn.execute(
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

    def delete(
        self,
        entry_id: int,
        scope_type: str,
        scope_value: str,
        conn: sqlite3.Connection | None = None,
    ) -> BindingRecord | None:
        previous = self.get(entry_id, scope_type, scope_value, conn=conn)
        if previous is None:
            return None
        if conn is not None:
            conn.execute(
                """
                DELETE FROM scope_bindings
                WHERE scope_type = ? AND scope_value = ? AND entry_id = ?
                """,
                (scope_type, scope_value, entry_id),
            )
        else:
            with get_conn() as local_conn:
                local_conn.execute(
                    """
                    DELETE FROM scope_bindings
                    WHERE scope_type = ? AND scope_value = ? AND entry_id = ?
                    """,
                    (scope_type, scope_value, entry_id),
                )
        return previous

    def get_for_entries(
        self,
        entry_ids: list[int],
        scope_type: str,
        scope_value: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, BindingRecord]:
        if not entry_ids:
            return {}
        placeholders = ", ".join("?" for _ in entry_ids)
        if conn is not None:
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
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(
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

    def list_for_entry(
        self,
        entry_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> list[BindingRecord]:
        if conn is not None:
            rows = conn.execute(
                """
                SELECT *
                FROM scope_bindings
                WHERE entry_id = ?
                ORDER BY scope_type, scope_value
                """,
                (entry_id,),
            ).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(
                    """
                    SELECT *
                    FROM scope_bindings
                    WHERE entry_id = ?
                    ORDER BY scope_type, scope_value
                    """,
                    (entry_id,),
                ).fetchall()
        return self._hydrate_rows(rows)

    def list_for_entries(
        self,
        entry_ids: list[int],
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, list[BindingRecord]]:
        if not entry_ids:
            return {}
        placeholders = ", ".join("?" for _ in entry_ids)
        if conn is not None:
            rows = conn.execute(
                f"""
                SELECT *
                FROM scope_bindings
                WHERE entry_id IN ({placeholders})
                ORDER BY entry_id, scope_type, scope_value
                """,
                entry_ids,
            ).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(
                    f"""
                    SELECT *
                    FROM scope_bindings
                    WHERE entry_id IN ({placeholders})
                    ORDER BY entry_id, scope_type, scope_value
                    """,
                    entry_ids,
                ).fetchall()
        grouped: dict[int, list[BindingRecord]] = defaultdict(list)
        for item in self._hydrate_rows(rows):
            grouped[int(item["entry_id"])].append(item)
        return grouped

    def clear_scope(
        self,
        project_id: int,
        scope_type: str,
        scope_value: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[BindingRecord]:
        if conn is not None:
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
        with get_conn() as local_conn:
            rows = local_conn.execute(
                """
                SELECT *
                FROM scope_bindings
                WHERE scope_type = ? AND scope_value = ?
                  AND entry_id IN (SELECT entry_id FROM entries WHERE project_id = ?)
                """,
                (scope_type, scope_value, project_id),
            ).fetchall()
            local_conn.execute(
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
        conn: sqlite3.Connection | None = None,
    ) -> list[BindingRecord]:
        if not scope_values:
            return []
        placeholders = ", ".join("?" for _ in scope_values)
        params = [scope_type, *scope_values, project_id]
        if conn is not None:
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
        with get_conn() as local_conn:
            rows = local_conn.execute(
                f"""
                SELECT *
                FROM scope_bindings
                WHERE scope_type = ?
                  AND scope_value IN ({placeholders})
                  AND entry_id IN (SELECT entry_id FROM entries WHERE project_id = ?)
                """,
                params,
            ).fetchall()
            local_conn.execute(
                f"""
                DELETE FROM scope_bindings
                WHERE scope_type = ?
                  AND scope_value IN ({placeholders})
                  AND entry_id IN (SELECT entry_id FROM entries WHERE project_id = ?)
                """,
                params,
            )
        return self._hydrate_rows(rows)

    def count_for_variant(self, variant_id: int, conn: sqlite3.Connection | None = None) -> int:
        if conn is not None:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM scope_bindings
                WHERE variant_id = ?
                """,
                (variant_id,),
            ).fetchone()
        else:
            with get_conn() as local_conn:
                row = local_conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM scope_bindings
                    WHERE variant_id = ?
                    """,
                    (variant_id,),
                ).fetchone()
        return int(row["count"] or 0)

    def binding_counts_for_entry(
        self,
        entry_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, int]:
        if conn is not None:
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
        with get_conn() as local_conn:
            rows = local_conn.execute(
                """
                SELECT variant_id, COUNT(*) AS count
                FROM scope_bindings
                WHERE entry_id = ?
                GROUP BY variant_id
                """,
                (entry_id,),
            ).fetchall()
        return {int(row["variant_id"]): int(row["count"] or 0) for row in rows}

    def _hydrate_rows(self, rows: list[dict[str, object]]) -> list[BindingRecord]:
        return [
            {
                "scope_type": str(row["scope_type"]),
                "scope_value": str(row["scope_value"]),
                "entry_id": int(row["entry_id"]),
                "variant_id": int(row["variant_id"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        ]


class ScopeBindingCommandRepository:
    def __init__(self, store: _ScopeBindingStore | None = None) -> None:
        self._store = store or _ScopeBindingStore()

    def upsert(
        self,
        entry_id: int,
        scope_type: str,
        scope_value: str,
        variant_id: int,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> int | None:
        return self._store.upsert(entry_id, scope_type, scope_value, variant_id, timestamp, conn=conn)

    def delete(
        self,
        entry_id: int,
        scope_type: str,
        scope_value: str,
        conn: sqlite3.Connection | None = None,
    ) -> BindingRecord | None:
        return self._store.delete(entry_id, scope_type, scope_value, conn=conn)

    def clear_scope(
        self,
        project_id: int,
        scope_type: str,
        scope_value: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[BindingRecord]:
        return self._store.clear_scope(project_id, scope_type, scope_value, conn=conn)

    def remove_scope_bindings(
        self,
        project_id: int,
        scope_type: str,
        scope_values: list[str],
        conn: sqlite3.Connection | None = None,
    ) -> list[BindingRecord]:
        return self._store.remove_scope_bindings(project_id, scope_type, scope_values, conn=conn)


class ScopeBindingQueryRepository:
    def __init__(self, store: _ScopeBindingStore | None = None) -> None:
        self._store = store or _ScopeBindingStore()

    def get(
        self,
        entry_id: int,
        scope_type: str,
        scope_value: str,
        conn: sqlite3.Connection | None = None,
    ) -> BindingRecord | None:
        return self._store.get(entry_id, scope_type, scope_value, conn=conn)

    def get_for_entries(
        self,
        entry_ids: list[int],
        scope_type: str,
        scope_value: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, BindingRecord]:
        return self._store.get_for_entries(entry_ids, scope_type, scope_value, conn=conn)

    def list_for_entry(
        self,
        entry_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> list[BindingRecord]:
        return self._store.list_for_entry(entry_id, conn=conn)

    def list_for_entries(
        self,
        entry_ids: list[int],
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, list[BindingRecord]]:
        return self._store.list_for_entries(entry_ids, conn=conn)

    def count_for_variant(self, variant_id: int, conn: sqlite3.Connection | None = None) -> int:
        return self._store.count_for_variant(variant_id, conn=conn)

    def binding_counts_for_entry(
        self,
        entry_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, int]:
        return self._store.binding_counts_for_entry(entry_id, conn=conn)


class BindingLookupService:
    def __init__(self, binding_queries: ScopeBindingQueryRepository | None = None) -> None:
        self._binding_queries = binding_queries or ScopeBindingQueryRepository()

    def get_binding(
        self,
        entry_id: int,
        scope_ref: Any,
        conn: sqlite3.Connection | None = None,
    ) -> BindingRecord | None:
        scope_type, scope_value = _scope_tuple(scope_ref)
        return self._binding_queries.get(entry_id, scope_type, scope_value, conn=conn)

    def get_bindings_for_entries(
        self,
        entry_ids: list[int],
        scope_ref: Any,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, BindingRecord]:
        scope_type, scope_value = _scope_tuple(scope_ref)
        return self._binding_queries.get_for_entries(entry_ids, scope_type, scope_value, conn=conn)

    def list_bindings_for_entries(
        self,
        entry_ids: list[int],
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, list[BindingRecord]]:
        return self._binding_queries.list_for_entries(entry_ids, conn=conn)

    def list_bindings_for_entry(
        self,
        entry_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> list[BindingRecord]:
        return self._binding_queries.list_for_entry(entry_id, conn=conn)

    def count_variant_bindings(self, variant_id: int, conn: sqlite3.Connection | None = None) -> int:
        return self._binding_queries.count_for_variant(variant_id, conn=conn)

    def binding_counts_for_entry(
        self,
        entry_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, int]:
        return self._binding_queries.binding_counts_for_entry(entry_id, conn=conn)


class BindingCommandService:
    def __init__(
        self,
        variant_commands: VariantCommandRepository | None = None,
        variant_queries: VariantQueryRepository | None = None,
        binding_commands: ScopeBindingCommandRepository | None = None,
        binding_lookup: BindingLookupService | None = None,
    ) -> None:
        self._variant_commands = variant_commands or VariantCommandRepository()
        self._variant_queries = variant_queries or VariantQueryRepository()
        self._binding_commands = binding_commands or ScopeBindingCommandRepository()
        self._binding_lookup = binding_lookup or BindingLookupService()

    def upsert_binding(
        self,
        entry_id: int,
        scope_type: str,
        scope_value: str,
        variant_id: int,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> int | None:
        return self._binding_commands.upsert(entry_id, scope_type, scope_value, variant_id, timestamp, conn=conn)

    def clear_scope_bindings(
        self,
        project_id: int,
        scope_type: str,
        scope_value: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[BindingRecord]:
        return self._binding_commands.clear_scope(project_id, scope_type, scope_value, conn=conn)

    def remove_scope_binding_rows(
        self,
        project_id: int,
        scope_type: str,
        scope_values: list[str],
        conn: sqlite3.Connection | None = None,
    ) -> list[BindingRecord]:
        return self._binding_commands.remove_scope_bindings(project_id, scope_type, scope_values, conn=conn)

    def bind_scope(
        self,
        entry_id: int,
        scope_ref: Any,
        variant_id: int,
        conn: sqlite3.Connection | None = None,
        timestamp: str | None = None,
    ) -> None:
        scope_type, scope_value = _scope_tuple(scope_ref)
        marker = timestamp or now_iso()
        self._binding_commands.upsert(
            entry_id,
            scope_type,
            scope_value,
            variant_id,
            marker,
            conn=conn,
        )
        self._variant_commands.clear_orphaned_at(variant_id, marker, conn=conn)

    def clear_scope(
        self,
        scope_ref: Any,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> None:
        scope_type, scope_value = _scope_tuple(scope_ref)
        self._binding_commands.clear_scope(project_id, scope_type, scope_value)

    def remove_scope_bindings(
        self,
        scope_refs: list[Any],
        project_id: int = DEFAULT_PROJECT_ID,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        grouped_scope_values: dict[str, list[str]] = {}
        for scope_ref in scope_refs:
            scope_type, scope_value = _scope_tuple(scope_ref)
            grouped_scope_values.setdefault(scope_type, []).append(scope_value)
        removed: list[BindingRecord] = []
        for scope_type, scope_values in grouped_scope_values.items():
            removed.extend(self.remove_scope_binding_rows(project_id, scope_type, scope_values, conn=conn))
        return len(removed)

    def remove_binding(
        self,
        entry_id: int,
        scope_ref: Any,
        conn: sqlite3.Connection | None = None,
    ) -> BindingRecord | None:
        scope_type, scope_value = _scope_tuple(scope_ref)
        removed = self._binding_commands.delete(entry_id, scope_type, scope_value, conn=conn)
        if removed is None:
            return None
        return removed
