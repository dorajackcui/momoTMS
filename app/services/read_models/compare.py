from __future__ import annotations

from app.services.branch.models import BranchRef
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.read_models._support import ReadModelSupport


class BranchCompareReadService(ReadModelSupport):
    def compare_branches(
        self,
        base_branch_ref: BranchRef,
        target_branch_ref: BranchRef,
        project_id: int = DEFAULT_PROJECT_ID,
        lang: str | None = None,
        search: str | None = None,
        states: list[str] | None = None,
        diff_categories: list[str] | None = None,
        priority_statuses: list[str] | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> dict:
        return self._compare_branches(
            base_branch_ref,
            target_branch_ref,
            project_id=project_id,
            lang=lang,
            search=search,
            states=states,
            diff_categories=diff_categories,
            priority_statuses=priority_statuses,
            page=page,
            page_size=page_size,
        )
