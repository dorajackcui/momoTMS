from __future__ import annotations

from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.read_models._support import ReadModelSupport


class BranchSummaryReadService(ReadModelSupport):
    def branch_summary(self, project_id: int = DEFAULT_PROJECT_ID, lang: str | None = None) -> dict:
        return self._branch_summary(project_id=project_id, lang=lang)
