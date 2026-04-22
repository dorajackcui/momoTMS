from __future__ import annotations

from time import perf_counter
from typing import Any

from app.db import get_conn
from app.services.branch.models import BranchRef
from app.services.branch.policy import BranchReplacePolicy
from app.services.branch.registry import BranchRegistryService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.read_models.derived.replace_preview import ReplacePreviewView
from app.services.read_models.repository import ReadModelRepository
from app.services.read_models.selectors import ScopeSelector
from app.services.shared.utils import now_iso
from app.services.variant.bindings import BindingCommandService
from app.services.variant.lifecycle import VariantLifecycleService


class BranchReplaceService:
    def __init__(self) -> None:
        self.preview_view = ReplacePreviewView()
        self.branch_registry = BranchRegistryService()
        self.read_models = ReadModelRepository()
        self.binding_commands = BindingCommandService()
        self.bindings = self.binding_commands
        self.lifecycle = VariantLifecycleService()

    def preview(
        self,
        source_branch_ref: BranchRef,
        target_branch_ref: BranchRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self.preview_view.build(
            source_branch_ref,
            target_branch_ref,
            project_id=project_id,
        )

    def execute(
        self,
        source_branch_ref: BranchRef,
        target_branch_ref: BranchRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        started = perf_counter()
        policy = BranchReplacePolicy.for_branches(source_branch_ref, target_branch_ref)
        preview = self.preview(source_branch_ref, target_branch_ref, project_id)
        cleanup_branch_refs = policy.cleanup_branch_refs(self.branch_registry, project_id)
        target_scope_type, target_scope_value = target_branch_ref.as_tuple()
        timestamp = now_iso()
        cleanup_binding_count = 0
        with get_conn() as conn:
            try:
                source_members = self.read_models.select_scope_member_rows(
                    project_id,
                    ScopeSelector.from_branch(source_branch_ref),
                    page=1,
                    page_size=None,
                    conn=conn,
                )
                removed_target_bindings = self.binding_commands.clear_bindings(
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
                removed_binding_rows = self._cleanup_bindings(cleanup_branch_refs, project_id, conn)
                cleanup_binding_count = len(removed_binding_rows)
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
            "target_entry_count": preview["summary"]["target_entry_count"],
            "added_to_target_count": preview["summary"]["added_to_target_count"],
            "kept_in_target_count": preview["summary"]["kept_in_target_count"],
            "rebind_target_count": preview["summary"]["rebind_target_count"],
            "removed_from_target_count": preview["summary"]["removed_from_target_count"],
            "cleanup_binding_count": cleanup_binding_count,
            "binding_effect_counts": dict(preview["summary"]["binding_effect_counts"]),
            "variant_resolution_counts": dict(preview["summary"]["variant_resolution_counts"]),
            "row_outcome_counts": dict(preview["summary"]["row_outcome_counts"]),
            "stages": [
                {
                    "stage": "execute_branch_replace",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {
                        "source_branch_ref": str(source_branch_ref),
                        "target_branch_ref": str(target_branch_ref),
                        "target_entry_count": preview["summary"]["target_entry_count"],
                    },
                }
            ],
        }
        return {"summary": summary, "report_rows": preview["rows"]}

    def _cleanup_bindings(
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
                self.binding_commands.remove_binding_rows(
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
