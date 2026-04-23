from __future__ import annotations

import sqlite3

from app.services.shared.utils import now_iso
from app.services.variant.bindings import BindingLookupService
from app.services.variant.repositories import VariantCommandRepository, VariantQueryRepository


class VariantLifecycleService:
    def __init__(
        self,
        variant_commands: VariantCommandRepository | None = None,
        variant_queries: VariantQueryRepository | None = None,
        binding_lookup: BindingLookupService | None = None,
    ) -> None:
        self._variant_commands = variant_commands or VariantCommandRepository()
        self._variant_queries = variant_queries or VariantQueryRepository()
        self._binding_lookup = binding_lookup or BindingLookupService()

    def refresh_orphan_states(
        self,
        entry_id: int,
        conn: sqlite3.Connection | None = None,
        timestamp: str | None = None,
    ) -> None:
        variant_rows = self._variant_queries.list_by_entry(entry_id, include_trashed=True, conn=conn)
        binding_counts = self._binding_lookup.binding_counts_for_entry(entry_id, conn=conn)
        marker = timestamp or now_iso()
        for variant in variant_rows:
            variant_id = int(variant["variant_id"])
            if variant["trashed_at"] is not None:
                orphaned_at = None
            elif binding_counts.get(variant_id, 0) == 0:
                orphaned_at = variant["orphaned_at"] or marker
            else:
                orphaned_at = None
            self._variant_commands.set_orphaned_at(variant_id, orphaned_at, conn=conn)

    def trash_orphan(
        self,
        variant_id: int,
        entry_id: int,
        conn: sqlite3.Connection | None = None,
        timestamp: str | None = None,
    ) -> None:
        marker = timestamp or now_iso()
        self._variant_commands.trash_variant(variant_id, marker, "", conn=conn)
        self.refresh_orphan_states(entry_id, conn=conn, timestamp=marker)
