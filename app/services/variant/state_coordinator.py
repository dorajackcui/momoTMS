from __future__ import annotations

import sqlite3
from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.utils import now_iso
from app.services.variant.bindings import BindingCommandService, BindingLookupService, _scope_tuple
from app.services.variant.lifecycle import VariantLifecycleService
from app.services.variant.records import BindingRecord
from app.services.variant.repositories import VariantCommandRepository, VariantQueryRepository


class VariantStateCoordinator:
    def __init__(
        self,
        variant_commands: VariantCommandRepository | None = None,
        variant_queries: VariantQueryRepository | None = None,
        binding_commands: BindingCommandService | None = None,
        binding_lookup: BindingLookupService | None = None,
        lifecycle: VariantLifecycleService | None = None,
    ) -> None:
        self._variant_commands = variant_commands or VariantCommandRepository()
        self._binding_lookup = binding_lookup or BindingLookupService()
        self._binding_commands = binding_commands or BindingCommandService(
            variant_commands=self._variant_commands,
            variant_queries=variant_queries,
            binding_lookup=self._binding_lookup,
        )
        self._lifecycle = lifecycle or VariantLifecycleService(
            variant_commands=self._variant_commands,
            variant_queries=variant_queries,
            binding_lookup=self._binding_lookup,
        )

    def bind_scope(
        self,
        entry_id: int,
        scope_ref: Any,
        variant_id: int,
        conn: sqlite3.Connection | None = None,
        timestamp: str | None = None,
    ) -> None:
        marker = timestamp or now_iso()
        self._binding_commands.bind_scope(entry_id, scope_ref, variant_id, conn=conn, timestamp=marker)
        self._lifecycle.refresh_orphan_states(entry_id, conn=conn, timestamp=marker)

    def clear_scope(
        self,
        scope_ref: Any,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> None:
        scope_type, scope_value = _scope_tuple(scope_ref)
        removed = self._binding_commands.clear_scope_bindings(project_id, scope_type, scope_value)
        for row in removed:
            self._lifecycle.refresh_orphan_states(int(row["entry_id"]))

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
            removed.extend(self._binding_commands.remove_scope_binding_rows(project_id, scope_type, scope_values, conn=conn))
        refreshed_entry_ids = sorted({int(row["entry_id"]) for row in removed})
        for entry_id in refreshed_entry_ids:
            self._lifecycle.refresh_orphan_states(entry_id, conn=conn)
        return len(removed)

    def remove_binding(
        self,
        entry_id: int,
        scope_ref: Any,
        conn: sqlite3.Connection | None = None,
    ) -> BindingRecord | None:
        removed = self._binding_commands.remove_binding(entry_id, scope_ref, conn=conn)
        if removed is None:
            return None
        self._lifecycle.refresh_orphan_states(int(removed["entry_id"]), conn=conn)
        return removed
