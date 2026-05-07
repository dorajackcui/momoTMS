from __future__ import annotations

from dataclasses import dataclass

from app.schemas import (
    VariantGridColumnFilter,
    VariantGridColumnRef,
    VariantGridFilterRequest,
    VariantGridQueryRequest,
)
from app.services.branch.models import BranchRef
from app.services.project.service import ProjectService
from app.services.read_models.selectors import ProjectLiveState, ScopeSelector
from app.services.shared.io import normalize_non_content_value


GRID_FIELD_NAMES = frozenset({
    "business_key",
    "file_name",
    "source",
    "branch",
    "state",
    "pivot_status",
})
MAX_GRID_PAGE_SIZE = 50
MAX_FILTER_OPTION_LIMIT = 100


@dataclass(frozen=True)
class GridColumnFilter:
    column: VariantGridColumnRef
    text: str
    values: tuple[str | None, ...]


@dataclass(frozen=True)
class GridQuerySpec:
    project_id: int
    scope_selector: ScopeSelector | None
    state: ProjectLiveState
    filters: tuple[GridColumnFilter, ...]
    page: int
    page_size: int


@dataclass(frozen=True)
class GridOptionsSpec:
    query: GridQuerySpec
    target_column: VariantGridColumnRef
    option_search: str
    limit: int


def build_grid_query(
    project_id: int,
    request: VariantGridQueryRequest,
    *,
    projects: ProjectService | None = None,
) -> GridQuerySpec:
    service = projects or ProjectService()
    schema = service.get_schema(project_id)
    scope_selector = _scope_selector(request)
    return GridQuerySpec(
        project_id=project_id,
        scope_selector=scope_selector,
        state=request.state if scope_selector is None else "active",
        filters=tuple(_validated_filter(item, schema) for item in request.filters),
        page=max(request.page, 1),
        page_size=min(max(request.page_size, 1), MAX_GRID_PAGE_SIZE),
    )


def build_grid_options(
    project_id: int,
    request: VariantGridFilterRequest,
    *,
    projects: ProjectService | None = None,
) -> GridOptionsSpec:
    if request.target_column is None:
        raise ValueError("target_column is required")
    service = projects or ProjectService()
    schema = service.get_schema(project_id)
    query = build_grid_query(project_id, request, projects=service)
    return GridOptionsSpec(
        query=query,
        target_column=_validated_column(request.target_column, schema),
        option_search=normalize_non_content_value(request.option_search).lower(),
        limit=min(max(request.limit, 1), MAX_FILTER_OPTION_LIMIT),
    )


def filters_excluding_target(
    filters: tuple[GridColumnFilter, ...],
    target_column: VariantGridColumnRef,
) -> tuple[GridColumnFilter, ...]:
    return tuple(item for item in filters if item.column != target_column)


def _scope_selector(request: VariantGridQueryRequest) -> ScopeSelector | None:
    if request.scope.kind == "project":
        return None
    branch_ref = normalize_non_content_value(request.scope.branch_ref)
    if not branch_ref:
        raise ValueError("branch_ref is required for branch scope")
    parsed = BranchRef.parse(branch_ref)
    if parsed.is_orphan:
        raise ValueError("branch_ref must be rel/current or dev/<version>")
    return ScopeSelector.from_branch(parsed)


def _validated_filter(
    item: VariantGridColumnFilter,
    schema: dict,
) -> GridColumnFilter:
    return GridColumnFilter(
        column=_validated_column(item.column, schema),
        text=normalize_non_content_value(item.text).lower(),
        values=tuple(_normalized_value(value) for value in item.values),
    )


def _validated_column(column: VariantGridColumnRef, schema: dict) -> VariantGridColumnRef:
    normalized_name = normalize_non_content_value(column.name)
    normalized = VariantGridColumnRef(kind=column.kind, name=normalized_name)
    if normalized.kind == "field":
        if normalized.name not in GRID_FIELD_NAMES:
            raise ValueError(f"unknown grid field for project: {normalized.name}")
        return normalized
    if normalized.kind == "translation":
        if normalized.name not in schema["translation_columns"]:
            raise ValueError(f"unknown translation column for project: {normalized.name}")
        return normalized
    if normalized.kind == "remark":
        if normalized.name not in schema["remark_columns"]:
            raise ValueError(f"unknown remark column for project: {normalized.name}")
        return normalized
    raise ValueError(f"unsupported grid column kind: {normalized.kind}")


def _normalized_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_non_content_value(value)
    return normalized if normalized else None
