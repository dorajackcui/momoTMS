from __future__ import annotations

import sqlite3
from typing import Any

from app.services.branch.models import BranchRef
from app.services.variant.records import BindingRecord, BindingSummary, EntryVariantView, ScopeEntryRecord
from app.services.variant.repositories import VariantQueryRepository


class ScopeEntryHydrator:
    def __init__(self, variant_queries: VariantQueryRepository | None = None) -> None:
        self._variant_queries = variant_queries or VariantQueryRepository()

    def hydrate(
        self,
        rows: list[dict[str, Any]],
        conn: sqlite3.Connection | None = None,
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
        variants_by_id = {
            variant["variant_id"]: variant
            for variant in self._variant_queries.hydrate_variant_rows(variant_rows, conn=conn)
        }
        return [
            {
                "entry_id": int(row["entry_id"]),
                "project_id": int(row["project_id"]),
                "business_key": row["business_key"],
                "variant": variants_by_id[int(row["variant_id"])],
                "scope_type": row["scope_type"],
                "scope_value": row["scope_value"],
                "created_at": row["entry_created_at"],
                "updated_at": row["entry_updated_at"],
            }
            for row in rows
        ]


class EntryVariantViewAssembler:
    def binding_summary(self, binding: BindingRecord) -> BindingSummary:
        return {
            "branch_ref": str(BranchRef.parse(f"{binding['scope_type']}/{binding['scope_value']}")),
            "created_at": binding["created_at"],
            "updated_at": binding["updated_at"],
        }

    def assemble(self, item: ScopeEntryRecord, bindings: list[BindingRecord]) -> EntryVariantView:
        variant = item["variant"]
        return {
            "variant_id": int(variant["variant_id"]),
            "entry_id": int(item["entry_id"]),
            "project_id": int(item["project_id"]),
            "business_key": item["business_key"],
            "file_name": variant["file_name"],
            "source": variant["source"],
            "translations": variant["translations"],
            "remarks": variant["remarks"],
            "bindings": [self.binding_summary(binding) for binding in bindings],
            "trashed_at": variant["trashed_at"],
            "trash_until": variant["trash_until"],
            "restored_at": variant["restored_at"],
            "created_at": variant["created_at"],
            "updated_at": variant["updated_at"],
        }


class ProjectVariantRowAssembler:
    def __init__(self) -> None:
        self._entry_variant_assembler = EntryVariantViewAssembler()

    def binding_summary(self, binding: BindingRecord) -> BindingSummary:
        return self._entry_variant_assembler.binding_summary(binding)
