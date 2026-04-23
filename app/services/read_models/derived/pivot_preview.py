from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.branch.models import BranchRef
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.read_models.datasets.live_variants import ProjectLiveVariantsDataset
from app.services.read_models.selectors import VariantFilter
from app.services.variant.records import PivotStatus


class PivotPreviewView:
    def __init__(self, *, live_variants: ProjectLiveVariantsDataset | None = None) -> None:
        self.live_variants = live_variants or ProjectLiveVariantsDataset()

    def build(
        self,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
        branch_ref: BranchRef | None = None,
        pivot_status: PivotStatus | None = "changed",
    ) -> dict[str, Any]:
        filters = VariantFilter(
            state="all",
            branch_refs=(branch_ref,) if branch_ref is not None else (),
            pivot_status=pivot_status,
        )
        result = self.live_variants.list(filters, project_id=project_id)
        rows = result.get("rows", [])
        by_branch: dict[str, int] = dict(
            Counter(
                row["pivot_changed_by_branch_ref"]
                for row in rows
                if row.get("pivot_changed_by_branch_ref")
            )
        )
        result["summary"] = {
            "total_count": len(rows),
            "by_branch": by_branch,
        }
        return result
