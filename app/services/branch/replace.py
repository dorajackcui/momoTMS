from __future__ import annotations

from time import perf_counter
from typing import Any

from app.db import get_conn
from app.services.branch.details import BranchDetailService
from app.services.branch.models import BranchRef
from app.services.branch.policy import BranchReplacePolicy
from app.services.branch.queries import BranchQueryRepository
from app.services.branch.registry import BranchRegistryService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.utils import now_iso
from app.services.variant.bindings import BindingCommandService
from app.services.variant.lifecycle import VariantLifecycleService


class BranchReplaceService:
    def __init__(self) -> None:
        self.branch_details = BranchDetailService()
        self.branch_registry = BranchRegistryService()
        self.branch_queries = BranchQueryRepository()
        self.binding_commands = BindingCommandService()
        self.bindings = self.binding_commands
        self.lifecycle = VariantLifecycleService()

    def preview(
        self,
        source_branch_ref: BranchRef,
        target_branch_ref: BranchRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        policy = BranchReplacePolicy.for_branches(source_branch_ref, target_branch_ref)
        source_entries = self.branch_details.list_branch_entries(source_branch_ref, project_id)
        target_entries = self.branch_details.list_branch_entries(target_branch_ref, project_id)
        source_keys = {item["business_key"] for item in source_entries}
        target_keys = {item["business_key"] for item in target_entries}
        added = sorted(source_keys - target_keys)
        already = sorted(source_keys & target_keys)
        removed = sorted(target_keys - source_keys)
        cleanup_branch_refs = policy.cleanup_branch_refs(self.branch_registry, self.branch_details, project_id)
        cleanup_binding_count = sum(
            self.branch_queries.count_scope_entries(project_id, *branch_ref.as_tuple())
            for branch_ref in cleanup_branch_refs
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
            "source_branch_ref": str(source_branch_ref),
            "target_branch_ref": str(target_branch_ref),
            "target_entry_count": len(source_keys),
            "added_to_target_count": len(added),
            "already_in_target_count": len(already),
            "removed_from_target_count": len(removed),
            "cleanup_binding_count": cleanup_binding_count,
            "report_rows": report_rows,
        }

    def execute(
        self,
        source_branch_ref: BranchRef,
        target_branch_ref: BranchRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        started = perf_counter()
        policy = BranchReplacePolicy.for_branches(source_branch_ref, target_branch_ref)
        preview = self.preview(source_branch_ref, target_branch_ref, project_id)
        cleanup_branch_refs = policy.cleanup_branch_refs(self.branch_registry, self.branch_details, project_id)
        target_scope_type, target_scope_value = target_branch_ref.as_tuple()
        source_scope_type, source_scope_value = source_branch_ref.as_tuple()
        timestamp = now_iso()
        removed_binding_count = 0
        with get_conn() as conn:
            try:
                source_members = self.branch_queries.list_scope_rows(
                    project_id,
                    source_scope_type,
                    source_scope_value,
                    conn=conn,
                )
                removed_target_bindings = self.binding_commands.clear_scope_bindings(
                    project_id,
                    target_scope_type,
                    target_scope_value,
                    conn=conn,
                )
                affected_entry_ids = {int(row["entry_id"]) for row in removed_target_bindings}
                for item in source_members:
                    entry_id = int(item["entry_id"])
                    affected_entry_ids.add(entry_id)
                    self.binding_commands.upsert_binding(
                        entry_id,
                        target_scope_type,
                        target_scope_value,
                        int(item["variant_id"]),
                        timestamp,
                        conn=conn,
                    )
                removed_binding_rows = self._cleanup_scope_bindings(cleanup_branch_refs, project_id, conn)
                removed_binding_count = len(removed_binding_rows)
                affected_entry_ids.update(int(row["entry_id"]) for row in removed_binding_rows)
                self._mark_cleanup_branches(cleanup_branch_refs, project_id, timestamp, conn)
                for entry_id in sorted(affected_entry_ids):
                    self.lifecycle.refresh_orphan_states(entry_id, conn=conn, timestamp=timestamp)
            except Exception:
                conn.rollback()
                raise
        summary = {
            "source_branch_ref": str(source_branch_ref),
            "target_branch_ref": str(target_branch_ref),
            "target_entry_count": preview["target_entry_count"],
            "added_to_target_count": preview["added_to_target_count"],
            "already_in_target_count": preview["already_in_target_count"],
            "removed_from_target_count": preview["removed_from_target_count"],
            "cleanup_binding_count": removed_binding_count,
            "stages": [
                {
                    "stage": "execute_branch_replace",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {
                        "source_branch_ref": str(source_branch_ref),
                        "target_branch_ref": str(target_branch_ref),
                        "target_entry_count": preview["target_entry_count"],
                    },
                }
            ],
        }
        return {"summary": summary, "report_rows": preview["report_rows"]}

    def _cleanup_scope_bindings(
        self,
        branch_refs: list[BranchRef],
        project_id: int,
        conn: Any,
    ) -> list[dict[str, Any]]:
        grouped_scope_values: dict[str, list[str]] = {}
        for branch_ref in branch_refs:
            scope_type, scope_value = branch_ref.as_tuple()
            grouped_scope_values.setdefault(scope_type, []).append(scope_value)
        removed_binding_rows: list[dict[str, Any]] = []
        for scope_type, scope_values in grouped_scope_values.items():
            removed_binding_rows.extend(
                self.binding_commands.remove_scope_binding_rows(
                    project_id,
                    scope_type,
                    scope_values,
                    conn=conn,
                )
            )
        return removed_binding_rows

    def _mark_cleanup_branches(
        self,
        branch_refs: list[BranchRef],
        project_id: int,
        timestamp: str,
        conn: Any,
    ) -> None:
        versions = [branch_ref.branch_value for branch_ref in branch_refs if branch_ref.is_dev]
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
