from __future__ import annotations

from app.services.branch.models import BranchRef
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.read_models._support import ReadModelSupport


class TranslationQueueReadService(ReadModelSupport):
    def translation_queue(
        self,
        target_branch_ref: BranchRef,
        project_id: int = DEFAULT_PROJECT_ID,
        lang: str | None = None,
        search: str | None = None,
        priority_statuses: list[str] | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> dict:
        return self._translation_queue(
            target_branch_ref,
            project_id=project_id,
            lang=lang,
            search=search,
            priority_statuses=priority_statuses,
            page=page,
            page_size=page_size,
        )
