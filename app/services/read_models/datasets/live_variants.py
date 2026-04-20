from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.hydrate import ReadModelHydrator
from app.services.read_models.repository import ReadModelRepository
from app.services.read_models.selectors import VariantFilter


class ProjectLiveVariantsDataset:
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

    def list(
        self,
        filters: VariantFilter,
        *,
        page: int = 1,
        page_size: int | None = None,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        payload = self.repository.list_live_variant_rows(
            project_id,
            filters,
            page=page,
            page_size=page_size,
        )
        return {
            "rows": self.hydrator.live_variants(payload["rows"]),
            "total_rows": payload["total_rows"],
            "page": payload["page"],
            "page_size": payload["page_size"],
        }
