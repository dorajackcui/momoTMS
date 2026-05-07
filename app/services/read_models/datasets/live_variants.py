from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.hydrate import ReadModelHydrator
from app.services.read_models.grid_filters import build_grid_options, build_grid_query
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

    def query(
        self,
        request,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        spec = build_grid_query(project_id, request, projects=self.projects)
        if spec.scope_selector is not None:
            raise ValueError("project scope is required")
        payload = self.repository.list_grid_variant_rows(spec)
        return {
            "rows": self.hydrator.live_variants(payload["rows"]),
            "total_rows": payload["total_rows"],
            "page": payload["page"],
            "page_size": payload["page_size"],
            "has_next_page": payload["has_next_page"],
            "total_rows_exact": payload["total_rows_exact"],
        }

    def filter_options(
        self,
        request,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        spec = build_grid_options(project_id, request, projects=self.projects)
        if spec.query.scope_selector is not None:
            raise ValueError("project scope is required")
        return self.repository.list_grid_filter_options(spec)
