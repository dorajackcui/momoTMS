from __future__ import annotations

import sqlite3
from typing import Any

from app.services.branch.models import BranchRef
from app.services.read_models.types import (
    BindingInfo,
    BranchEntryView,
    EntryTimelineItem,
    HistoryCandidate,
    LiveVariantRow,
    ScopeMember,
    VariantSnapshot,
)
from app.services.variant.bindings import BindingLookupService
from app.services.variant.pivot import pivot_changed_by_branch_ref
from app.services.variant.records import BindingRecord, VariantRecord
from app.services.variant.repositories import VariantQueryRepository


class ReadModelHydrator:
    def __init__(
        self,
        *,
        variant_queries: VariantQueryRepository | None = None,
        bindings: BindingLookupService | None = None,
    ) -> None:
        self.variant_queries = variant_queries or VariantQueryRepository()
        self.bindings = bindings or BindingLookupService()

    def scope_members(
        self,
        rows: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> list[ScopeMember]:
        if not rows:
            return []
        variants_by_id = self._variants_by_id(rows, conn=conn)
        bindings_by_entry = self._bindings_by_entry(rows, conn=conn)
        results: list[ScopeMember] = []
        for row in rows:
            variant = variants_by_id[int(row["variant_id"])]
            variant_bindings = self._variant_bindings(
                int(row["entry_id"]),
                int(variant["variant_id"]),
                bindings_by_entry,
            )
            state = self._resolve_state(variant, variant_bindings)
            results.append(
                {
                    "variant_id": int(variant["variant_id"]),
                    "entry_id": int(row["entry_id"]),
                    "business_key": row["business_key"],
                    "file_name": variant["file_name"],
                    "source": variant["source"],
                    "translations": variant["translations"],
                    "remarks": variant["remarks"],
                    "bindings": variant_bindings,
                    "state": "active" if state == "active" else "orphan",
                    "orphaned_at": variant["orphaned_at"] if state == "orphan" else None,
                    "pivot_status": variant["pivot_status"],
                    "pivot_changed_by_branch_ref": pivot_changed_by_branch_ref(variant),
                    "pivot_changed_at": variant["pivot_changed_at"],
                    "pivot_reviewed_at": variant["pivot_reviewed_at"],
                    "created_at": variant["created_at"],
                    "updated_at": variant["updated_at"],
                }
            )
        return results

    def live_variants(
        self,
        rows: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> list[LiveVariantRow]:
        return self.scope_members(rows, conn=conn)

    def history_candidates(
        self,
        rows: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> list[HistoryCandidate]:
        if not rows:
            return []
        variants_by_id = self._variants_by_id(rows, conn=conn)
        bindings_by_entry = self._bindings_by_entry(rows, conn=conn)
        results: list[HistoryCandidate] = []
        for row in rows:
            variant = variants_by_id[int(row["variant_id"])]
            variant_bindings = self._variant_bindings(
                int(row["entry_id"]),
                int(variant["variant_id"]),
                bindings_by_entry,
            )
            state = self._resolve_state(variant, variant_bindings)
            results.append(
                {
                    "variant_id": int(variant["variant_id"]),
                    "entry_id": int(row["entry_id"]),
                    "business_key": row["business_key"],
                    "file_name": variant["file_name"],
                    "source": variant["source"],
                    "translations": variant["translations"],
                    "remarks": variant["remarks"],
                    "bindings": variant_bindings,
                    "state": state,
                    "orphaned_at": variant["orphaned_at"],
                    "trashed_at": variant["trashed_at"],
                    "trash_until": variant["trash_until"],
                    "restored_at": variant["restored_at"],
                    "pivot_status": variant["pivot_status"],
                    "pivot_changed_by_branch_ref": pivot_changed_by_branch_ref(variant),
                    "pivot_changed_at": variant["pivot_changed_at"],
                    "pivot_reviewed_at": variant["pivot_reviewed_at"],
                    "created_at": variant["created_at"],
                    "updated_at": variant["updated_at"],
                }
            )
        return results

    def entry_timeline_items(
        self,
        rows: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> list[EntryTimelineItem]:
        if not rows:
            return []
        variants_by_id = self._variants_by_id(rows, conn=conn)
        bindings_by_entry = self._bindings_by_entry(rows, conn=conn)
        results: list[EntryTimelineItem] = []
        for row in rows:
            variant = variants_by_id[int(row["variant_id"])]
            variant_bindings = self._variant_bindings(
                int(row["entry_id"]),
                int(variant["variant_id"]),
                bindings_by_entry,
            )
            state = self._resolve_state(variant, variant_bindings)
            results.append(
                {
                    "variant_id": int(variant["variant_id"]),
                    "file_name": variant["file_name"],
                    "source": variant["source"],
                    "translations": variant["translations"],
                    "remarks": variant["remarks"],
                    "bindings": variant_bindings,
                    "is_orphaned": state == "orphan",
                    "is_trashed": state == "trashed",
                    "orphaned_at": variant["orphaned_at"],
                    "trashed_at": variant["trashed_at"],
                    "trash_until": variant["trash_until"],
                    "restored_at": variant["restored_at"],
                    "pivot_status": variant["pivot_status"],
                    "pivot_changed_by_branch_ref": pivot_changed_by_branch_ref(variant),
                    "pivot_changed_at": variant["pivot_changed_at"],
                    "pivot_reviewed_at": variant["pivot_reviewed_at"],
                    "created_at": variant["created_at"],
                    "updated_at": variant["updated_at"],
                }
            )
        return sorted(results, key=lambda item: item["variant_id"])

    def branch_entry_views(
        self,
        rows: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> list[BranchEntryView]:
        if not rows:
            return []
        variants_by_id = self._variants_by_id(rows, conn=conn)
        bindings_by_entry = self._bindings_by_entry(rows, conn=conn)
        results: list[BranchEntryView] = []
        for row in rows:
            variant = variants_by_id[int(row["variant_id"])]
            results.append(
                {
                    "variant_id": int(variant["variant_id"]),
                    "entry_id": int(row["entry_id"]),
                    "project_id": int(row["project_id"]),
                    "business_key": row["business_key"],
                    "file_name": variant["file_name"],
                    "source": variant["source"],
                    "translations": variant["translations"],
                    "remarks": variant["remarks"],
                    "bindings": self._variant_bindings(
                        int(row["entry_id"]),
                        int(variant["variant_id"]),
                        bindings_by_entry,
                    ),
                    "trashed_at": variant["trashed_at"],
                    "trash_until": variant["trash_until"],
                    "restored_at": variant["restored_at"],
                    "created_at": variant["created_at"],
                    "updated_at": variant["updated_at"],
                }
            )
        return results

    def binding_info(self, binding: BindingRecord) -> BindingInfo:
        return {
            "branch_ref": str(BranchRef.parse(f"{binding['scope_type']}/{binding['scope_value']}")),
            "created_at": binding["created_at"],
            "updated_at": binding["updated_at"],
        }

    def variant_snapshot(self, variant: VariantRecord) -> VariantSnapshot:
        return {
            "variant_id": int(variant["variant_id"]),
            "entry_id": int(variant["entry_id"]),
            "file_name": variant["file_name"],
            "source": variant["source"],
            "translations": variant["translations"],
            "remarks": variant["remarks"],
            "orphaned_at": variant["orphaned_at"],
            "trashed_at": variant["trashed_at"],
            "trash_until": variant["trash_until"],
            "restored_at": variant["restored_at"],
            "pivot_status": variant["pivot_status"],
            "pivot_changed_by_branch_ref": pivot_changed_by_branch_ref(variant),
            "pivot_changed_at": variant["pivot_changed_at"],
            "pivot_reviewed_at": variant["pivot_reviewed_at"],
            "created_at": variant["created_at"],
            "updated_at": variant["updated_at"],
        }

    def _variants_by_id(
        self,
        rows: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, VariantRecord]:
        return {
            int(variant["variant_id"]): variant
            for variant in self.variant_queries.hydrate_variant_rows(rows, conn=conn)
        }

    def _bindings_by_entry(
        self,
        rows: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[int, list[BindingRecord]]:
        entry_ids = sorted({int(row["entry_id"]) for row in rows})
        return self.bindings.list_bindings_for_entries(entry_ids, conn=conn)

    def _variant_bindings(
        self,
        entry_id: int,
        variant_id: int,
        bindings_by_entry: dict[int, list[BindingRecord]],
    ) -> list[BindingInfo]:
        items = [
            self.binding_info(binding)
            for binding in bindings_by_entry.get(entry_id, [])
            if int(binding["variant_id"]) == variant_id
        ]
        return sorted(items, key=lambda item: item["branch_ref"])

    def _resolve_state(
        self,
        variant: VariantRecord,
        bindings: list[BindingInfo],
    ) -> str:
        if variant["trashed_at"] is not None:
            return "trashed"
        if bindings:
            return "active"
        return "orphan"
