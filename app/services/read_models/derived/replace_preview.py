from __future__ import annotations

from typing import Any

from app.services.branch.models import BranchRef
from app.services.branch.preview_contract import effect_forecast_row
from app.services.branch.policy import BranchReplacePolicy
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.read_models.datasets.scope_members import ScopeMembershipDataset
from app.services.read_models.selectors import ScopeSelector, VariantFilter


class ReplacePreviewView:
    def __init__(
        self,
        *,
        scope_members: ScopeMembershipDataset | None = None,
    ) -> None:
        self.scope_members = scope_members or ScopeMembershipDataset()

    def build(
        self,
        source_branch_ref: BranchRef,
        target_branch_ref: BranchRef,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        _ = BranchReplacePolicy.for_branches(source_branch_ref, target_branch_ref)
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
        rows = [
            effect_forecast_row(
                {"business_key": key, "status": "ADD_TO_TARGET"},
                binding_effect="bind",
                variant_resolution="reuse_existing",
                row_outcome="applied",
            )
            for key in added
        ]
        rows.extend(
            effect_forecast_row(
                {"business_key": key, "status": "KEEP_IN_TARGET"},
                binding_effect="none",
                variant_resolution="stay_current",
                row_outcome="noop",
            )
            for key in kept
        )
        rows.extend(
            effect_forecast_row(
                {"business_key": key, "status": "REBIND_TARGET"},
                binding_effect="rebind",
                variant_resolution="reuse_existing",
                row_outcome="applied",
            )
            for key in rebind
        )
        rows.extend(
            effect_forecast_row(
                {"business_key": key, "status": "REMOVE_FROM_TARGET"},
                row_outcome="applied",
            )
            for key in removed
        )
        summary = {
            "final_target_entry_count": len(source_keys),
            "added_to_target_count": len(added),
            "kept_in_target_count": len(kept),
            "rebind_target_count": len(rebind),
            "removed_from_target_count": len(removed),
        }
        return {
            "preview_kind": "effect_forecast",
            "workflow_kind": "branch_replace",
            "request_echo": {
                "source_branch_ref": str(source_branch_ref),
                "target_branch_ref": str(target_branch_ref),
            },
            "summary": summary,
            "rows": rows,
        }
