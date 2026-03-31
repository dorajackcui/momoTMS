from __future__ import annotations

import sqlite3

from app.services.shared.io import (
    normalize_content_map,
    normalize_non_content_map,
    normalize_non_content_value,
)
from app.services.shared.utils import now_iso
from app.services.variant.normalization import require_non_content_value
from app.services.variant.pivot import VariantPivotCoordinator
from app.services.variant.records import VariantContent, VariantRecord
from app.services.variant.repositories import VariantCommandRepository, VariantQueryRepository


class VariantCatalogService:
    def __init__(
        self,
        variant_commands: VariantCommandRepository | None = None,
        variant_queries: VariantQueryRepository | None = None,
        pivot: VariantPivotCoordinator | None = None,
    ) -> None:
        self._commands = variant_commands or VariantCommandRepository()
        self._queries = variant_queries or VariantQueryRepository()
        self._pivot = pivot or VariantPivotCoordinator(variant_queries=self._queries)

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
        actor_scope: tuple[str, str] | None = None,
        restore_if_trashed: bool = False,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        previous_variant = self.get_variant(variant_id, conn=conn)
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
        self._pivot.refresh_variant(
            variant_id=variant_id,
            old_variant=previous_variant,
            new_translations=content["translations"],
            actor_scope=actor_scope,
            timestamp=timestamp,
            conn=conn,
        )

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
