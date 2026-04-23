from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.services.branch.models import BranchRef
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.repository import ReadModelRepository


class BranchSummaryView:
    def __init__(
        self,
        *,
        projects: ProjectService | None = None,
        repository: ReadModelRepository | None = None,
    ) -> None:
        self.projects = projects or ProjectService()
        self.repository = repository or ReadModelRepository()

    def build(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        *,
        lang: str | None = None,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        rows = self.repository.list_active_branch_projections(project_id, lang=lang)
        branch_order: list[str] = []
        branch_meta: dict[str, dict[str, Any]] = {}
        projections_by_branch: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in rows:
            branch_ref = row["branch_ref"]
            if branch_ref not in branch_meta:
                branch_order.append(branch_ref)
                branch_meta[branch_ref] = {"version_series": row["version_series"]}
            if row["variant_id"] is None or not row["business_key"]:
                continue
            projections_by_branch[branch_ref][row["business_key"]] = row

        rel_branch_ref = str(BranchRef.rel_current())
        rel_projection = projections_by_branch.get(rel_branch_ref, {})
        branches: list[dict[str, Any]] = []
        for branch_ref in branch_order:
            projection = projections_by_branch.get(branch_ref, {})
            if branch_ref == rel_branch_ref:
                status_counts = {
                    "aligned": len(projection),
                    "diverged": 0,
                    "base_only": 0,
                    "target_only": 0,
                }
            else:
                status_counts = self._status_counts(rel_projection, projection)
            item = {
                "branch_ref": branch_ref,
                "entry_count": len(projection),
                "status_counts": status_counts,
            }
            if branch_meta[branch_ref]["version_series"] is not None:
                item["version_series"] = branch_meta[branch_ref]["version_series"]
            branches.append(item)
        orphan_count = self._count_orphan_variants(project_id)
        if orphan_count > 0:
            branches.append(
                {
                    "branch_ref": "orphan",
                    "entry_count": orphan_count,
                    "status_counts": {"orphan": orphan_count},
                }
            )
        return {"branches": branches}

    def _count_orphan_variants(self, project_id: int) -> int:
        from app.services.read_models.selectors import ScopeSelector
        return self.repository.count_scope_members(project_id, ScopeSelector.orphan())

    def _status_counts(
        self,
        base_projection: dict[str, dict[str, Any]],
        target_projection: dict[str, dict[str, Any]],
    ) -> dict[str, int]:
        counts = {"aligned": 0, "diverged": 0, "base_only": 0, "target_only": 0}
        for business_key in sorted(set(base_projection) | set(target_projection)):
            state = self._branch_state(
                base_projection.get(business_key),
                target_projection.get(business_key),
            )
            counts[state] = counts.get(state, 0) + 1
        return counts

    def _branch_state(
        self,
        base_item: dict[str, Any] | None,
        target_item: dict[str, Any] | None,
    ) -> str:
        if base_item and not target_item:
            return "base_only"
        if target_item and not base_item:
            return "target_only"
        if not base_item and not target_item:
            return "target_only"
        if (
            base_item["source"] != target_item["source"]
            or base_item["translations_fingerprint"] != target_item["translations_fingerprint"]
            or base_item["remarks_fingerprint"] != target_item["remarks_fingerprint"]
            or base_item["file_name"] != target_item["file_name"]
        ):
            return "diverged"
        return "aligned"
