from __future__ import annotations

from time import perf_counter
from typing import Any

from app.db import get_conn
from app.services.branch.models import ScopeRef
from app.services.branch.policy import ScopeSyncPolicy
from app.services.branch.service import BranchService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.utils import now_iso
from app.services.variant.services import ScopeBindingService, VariantCatalogService, VariantLifecycleService


class BranchSyncService:
    def __init__(self) -> None:
        self.branch = BranchService()
        self.bindings = ScopeBindingService()
        self.catalog = VariantCatalogService()
        self.lifecycle = VariantLifecycleService()

    def preview(
        self,
        source_scope_ref: ScopeRef,
        target_scope_ref: ScopeRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        policy = ScopeSyncPolicy.for_scopes(source_scope_ref, target_scope_ref)
        source_entries = self.branch.list_scope_entries(source_scope_ref, project_id)
        target_entries = self.branch.list_scope_entries(target_scope_ref, project_id)
        source_keys = {item["business_key"] for item in source_entries}
        target_keys = {item["business_key"] for item in target_entries}
        added = sorted(source_keys - target_keys)
        already = sorted(source_keys & target_keys)
        removed = sorted(target_keys - source_keys)
        cleanup_scope_refs = policy.cleanup_scope_refs(self.branch, project_id)
        cleanup_binding_count = sum(
            self.bindings.count_scope(scope_ref, project_id)
            for scope_ref in cleanup_scope_refs
        )
        report_rows = [
            {"business_key": key, "status": "ADD_TO_TARGET"}
            for key in added
        ] + [
            {"business_key": key, "status": "KEEP_IN_TARGET"}
            for key in already
        ] + [
            {"business_key": key, "status": "REMOVE_FROM_TARGET"}
            for key in removed
        ]
        return {
            "source_scope_ref": str(source_scope_ref),
            "target_scope_ref": str(target_scope_ref),
            "target_entry_count": len(source_keys),
            "added_to_target_count": len(added),
            "already_in_target_count": len(already),
            "removed_from_target_count": len(removed),
            "cleanup_binding_count": cleanup_binding_count,
            "report_rows": report_rows,
        }

    def execute(
        self,
        source_scope_ref: ScopeRef,
        target_scope_ref: ScopeRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        started = perf_counter()
        policy = ScopeSyncPolicy.for_scopes(source_scope_ref, target_scope_ref)
        preview = self.preview(source_scope_ref, target_scope_ref, project_id)
        cleanup_scope_refs = policy.cleanup_scope_refs(self.branch, project_id)
        target_scope_type, target_scope_value = target_scope_ref.as_tuple()
        source_scope_type, source_scope_value = source_scope_ref.as_tuple()
        timestamp = now_iso()
        removed_binding_count = 0
        with get_conn() as conn:
            try:
                source_members = self.bindings.bindings.list_scope_entries(
                    project_id,
                    source_scope_type,
                    source_scope_value,
                    self.catalog.variants,
                    conn=conn,
                )
                removed_target_bindings = self.bindings.bindings.clear_scope(
                    project_id,
                    target_scope_type,
                    target_scope_value,
                    conn=conn,
                )
                affected_entry_ids = {int(row["entry_id"]) for row in removed_target_bindings}
                for item in source_members:
                    entry_id = int(item["entry_id"])
                    affected_entry_ids.add(entry_id)
                    self.bindings.bindings.upsert(
                        entry_id,
                        target_scope_type,
                        target_scope_value,
                        int(item["variant"]["variant_id"]),
                        timestamp,
                        conn=conn,
                    )
                removed_binding_rows = self._cleanup_scope_bindings(cleanup_scope_refs, project_id, conn)
                removed_binding_count = len(removed_binding_rows)
                affected_entry_ids.update(int(row["entry_id"]) for row in removed_binding_rows)
                self._mark_cleanup_scopes(cleanup_scope_refs, project_id, timestamp, conn)
                for entry_id in sorted(affected_entry_ids):
                    self.lifecycle.refresh_orphan_states(entry_id, conn=conn, timestamp=timestamp)
            except Exception:
                conn.rollback()
                raise
        summary = {
            "source_scope_ref": str(source_scope_ref),
            "target_scope_ref": str(target_scope_ref),
            "target_entry_count": preview["target_entry_count"],
            "added_to_target_count": preview["added_to_target_count"],
            "already_in_target_count": preview["already_in_target_count"],
            "removed_from_target_count": preview["removed_from_target_count"],
            "cleanup_binding_count": removed_binding_count,
            "stages": [
                {
                    "stage": "execute_scope_sync",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {
                        "source_scope_ref": str(source_scope_ref),
                        "target_scope_ref": str(target_scope_ref),
                        "target_entry_count": preview["target_entry_count"],
                    },
                }
            ],
        }
        return {"summary": summary, "report_rows": preview["report_rows"]}

    def _cleanup_scope_bindings(
        self,
        scope_refs: list[ScopeRef],
        project_id: int,
        conn: Any,
    ) -> list[dict[str, Any]]:
        grouped_scope_values: dict[str, list[str]] = {}
        for scope_ref in scope_refs:
            scope_type, scope_value = scope_ref.as_tuple()
            grouped_scope_values.setdefault(scope_type, []).append(scope_value)
        removed_binding_rows: list[dict[str, Any]] = []
        for scope_type, scope_values in grouped_scope_values.items():
            removed_binding_rows.extend(
                self.bindings.bindings.remove_scope_bindings(
                    project_id,
                    scope_type,
                    scope_values,
                    conn=conn,
                )
            )
        return removed_binding_rows

    def _mark_cleanup_scopes(
        self,
        scope_refs: list[ScopeRef],
        project_id: int,
        timestamp: str,
        conn: Any,
    ) -> None:
        versions = [scope_ref.scope_value for scope_ref in scope_refs if scope_ref.is_dev]
        if not versions:
            return
        placeholders = ", ".join("?" for _ in versions)
        conn.execute(
            f"""
            UPDATE dev_versions
            SET promoted_at = ?, is_candidate_release = 0
            WHERE project_id = ? AND version IN ({placeholders})
            """,
            [timestamp, project_id, *versions],
        )
