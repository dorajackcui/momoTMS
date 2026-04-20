from __future__ import annotations

from typing import Any

from app.services.branch.models import BranchRef
from app.services.branch.policy import BranchReplacePolicy
from app.services.branch.registry import BranchRegistryService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.read_models.datasets.scope_members import ScopeMembershipDataset
from app.services.read_models.repository import ReadModelRepository
from app.services.read_models.selectors import ScopeSelector, VariantFilter


class ReplacePreviewView:
    def __init__(
        self,
        *,
        scope_members: ScopeMembershipDataset | None = None,
        branch_registry: BranchRegistryService | None = None,
        repository: ReadModelRepository | None = None,
    ) -> None:
        self.scope_members = scope_members or ScopeMembershipDataset()
        self.branch_registry = branch_registry or BranchRegistryService()
        self.repository = repository or ReadModelRepository()

    def build(
        self,
        source_branch_ref: BranchRef,
        target_branch_ref: BranchRef,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        policy = BranchReplacePolicy.for_branches(source_branch_ref, target_branch_ref)
        source_payload = self.scope_members.list(
            ScopeSelector.from_branch(source_branch_ref),
            filters=VariantFilter(state="all"),
            project_id=project_id,
        )
        target_payload = self.scope_members.list(
            ScopeSelector.from_branch(target_branch_ref),
            filters=VariantFilter(state="all"),
            project_id=project_id,
        )
        source_rows = {item["business_key"]: item for item in source_payload["rows"]}
        target_rows = {item["business_key"]: item for item in target_payload["rows"]}
        source_keys = set(source_rows)
        target_keys = set(target_rows)
        added = sorted(source_keys - target_keys)
        kept = sorted(
            key
            for key in source_keys & target_keys
            if int(source_rows[key]["variant_id"]) == int(target_rows[key]["variant_id"])
        )
        rebind = sorted(
            key
            for key in source_keys & target_keys
            if int(source_rows[key]["variant_id"]) != int(target_rows[key]["variant_id"])
        )
        removed = sorted(target_keys - source_keys)
        cleanup_branch_refs = policy.cleanup_branch_refs(self.branch_registry, project_id)
        cleanup_binding_count = sum(
            self.repository.count_scope_members(project_id, ScopeSelector.from_branch(branch_ref))
            for branch_ref in cleanup_branch_refs
        )
        report_rows = [{"business_key": key, "status": "ADD_TO_TARGET"} for key in added]
        report_rows.extend({"business_key": key, "status": "KEEP_IN_TARGET"} for key in kept)
        report_rows.extend({"business_key": key, "status": "REBIND_TARGET"} for key in rebind)
        report_rows.extend({"business_key": key, "status": "REMOVE_FROM_TARGET"} for key in removed)
        return {
            "source_branch_ref": str(source_branch_ref),
            "target_branch_ref": str(target_branch_ref),
            "target_entry_count": len(source_keys),
            "added_to_target_count": len(added),
            "kept_in_target_count": len(kept),
            "rebind_target_count": len(rebind),
            "removed_from_target_count": len(removed),
            "cleanup_binding_count": cleanup_binding_count,
            "report_rows": report_rows,
        }
