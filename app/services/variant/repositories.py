from __future__ import annotations

import sqlite3
from typing import Any

from app.services.variant.records import VariantRecord
from app.services.variant.store import _VariantStore


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

    def set_pivot_changed(
        self,
        variant_id: int,
        scope_type: str,
        scope_value: str,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self._store.set_pivot_changed(variant_id, scope_type, scope_value, timestamp, conn=conn)

    def set_pivot_reviewed(
        self,
        variant_id: int,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self._store.set_pivot_reviewed(variant_id, timestamp, conn=conn)


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
