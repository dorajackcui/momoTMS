from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.hydrate import ReadModelHydrator
from app.services.read_models.grid_filters import build_grid_query
from app.services.read_models.repository import ReadModelRepository
from app.services.read_models.selectors import ScopeSelector, VariantFilter


class ScopeMembershipDataset:
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
        scope_selector: ScopeSelector,
        *,
        filters: VariantFilter | None = None,
        page: int = 1,
        page_size: int | None = None,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        filter_value = filters or VariantFilter()
        rows = self.repository.select_scope_member_rows(
            project_id,
            scope_selector,
            search_business_key=filter_value.search_business_key,
            search_source=filter_value.search_source,
            page=page,
            page_size=page_size,
        )
        total_rows = self.repository.count_scope_members(
            project_id,
            scope_selector,
            search_business_key=filter_value.search_business_key,
            search_source=filter_value.search_source,
        )
        page_size_value = page_size if page_size is not None and page_size > 0 else total_rows
        return {
            "scope_ref": str(scope_selector),
            "rows": self.hydrator.scope_members(rows),
            "total_rows": total_rows,
            "page": max(page, 1) if page_size is not None and page_size > 0 else 1,
            "page_size": page_size_value,
        }

    def query(
        self,
        request,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        spec = build_grid_query(project_id, request, projects=self.projects)
        if spec.scope_selector is None:
            raise ValueError("branch scope is required")
        payload = self.repository.list_grid_variant_rows(spec)
        return {
            "scope_ref": str(spec.scope_selector),
            "rows": self.hydrator.scope_members(payload["rows"]),
            "total_rows": payload["total_rows"],
            "page": payload["page"],
            "page_size": payload["page_size"],
            "has_next_page": payload["has_next_page"],
            "total_rows_exact": payload["total_rows_exact"],
        }

    def lookup(
        self,
        scope_selector: ScopeSelector,
        *,
        business_key: str | None = None,
        source: str | None = None,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        has_business_key = bool(business_key and business_key.strip())
        has_source = bool(source and source.strip())
        if has_business_key == has_source:
            raise ValueError("provide exactly one of business_key or source")
        rows = self.repository.select_scope_member_rows(
            project_id,
            scope_selector,
            business_key=business_key,
            source=source,
            page=1,
            page_size=None,
        )
        mode = "business_key" if has_business_key else "source"
        value = business_key if has_business_key else source
        return {
            "scope_ref": str(scope_selector),
            "mode": mode,
            "value": (value or "").strip(),
            "rows": self.hydrator.scope_members(rows),
        }

    def list_entry_views(
        self,
        scope_selector: ScopeSelector,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> list[dict[str, Any]]:
        self.projects.require_project(project_id)
        rows = self.repository.select_scope_member_rows(
            project_id,
            scope_selector,
            page=1,
            page_size=None,
        )
        return self.hydrator.branch_entry_views(rows)
