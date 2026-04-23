from __future__ import annotations

from time import perf_counter
from typing import Any

from app.db import get_conn
from app.services.branch.models import BranchRef
from app.services.branch.policy import BranchReplacePolicy
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
        self.read_models = ReadModelRepository()
        self.binding_commands = BindingCommandService()
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
        _ = BranchReplacePolicy.for_branches(source_branch_ref, target_branch_ref)
        preview = self.preview(source_branch_ref, target_branch_ref, project_id)
        target_scope_type, target_scope_value = target_branch_ref.as_tuple()
        timestamp = now_iso()
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
                for entry_id in sorted(affected_entry_ids):
                    self.lifecycle.refresh_orphan_states(entry_id, conn=conn, timestamp=timestamp)
            except Exception:
                conn.rollback()
                raise
        summary = {
            "source_branch_ref": str(source_branch_ref),
            "target_branch_ref": str(target_branch_ref),
            "final_target_entry_count": preview["summary"]["final_target_entry_count"],
            "added_to_target_count": preview["summary"]["added_to_target_count"],
            "kept_in_target_count": preview["summary"]["kept_in_target_count"],
            "rebind_target_count": preview["summary"]["rebind_target_count"],
            "removed_from_target_count": preview["summary"]["removed_from_target_count"],
            "stages": [
                {
                    "stage": "execute_branch_replace",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {
                        "source_branch_ref": str(source_branch_ref),
                        "target_branch_ref": str(target_branch_ref),
                        "final_target_entry_count": preview["summary"]["final_target_entry_count"],
                    },
                }
            ],
        }
        return {"summary": summary, "report_rows": preview["rows"]}
