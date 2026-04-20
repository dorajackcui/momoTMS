from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.hydrate import ReadModelHydrator
from app.services.read_models.repository import ReadModelRepository
from app.services.read_models.selectors import HistorySelector


class ProjectHistoryDataset:
    def __init__(
        self,
        *,
        projects: ProjectService | None = None,
        repository: ReadModelRepository | None = None,
        hydrator: ReadModelHydrator | None = None,
    ) -> None:
        self.projects = projects or ProjectService()
        self.repository = repository or ReadModelRepository()
        self.hydrator = hydrator or ReadModelHydrator()

    def same_source_candidates(
        self,
        business_key: str,
        source: str,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        selector = HistorySelector.same_source(business_key, source)
        rows = self.repository.list_same_source_history_rows(
            project_id,
            selector.business_key or "",
            selector.source or "",
        )
        return {
            "business_key": selector.business_key or "",
            "source": selector.source or "",
            "rows": self.hydrator.history_candidates(rows),
        }

    def fill_candidates(
        self,
        lang: str,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> list[dict[str, Any]]:
        self.projects.require_project(project_id)
        selector = HistorySelector.fill(lang)
        return self.repository.list_fill_candidate_rows(project_id, selector.lang or "")
