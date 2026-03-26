from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from app.routers.common import handle_errors, parse_branch_ref
from app.schemas import EntryVariantsResponse, OrphanVariantsResponse, ProjectVariantsResponse
from app.services.read_models.inspection import InspectionReadService
from app.services.read_models.variants import ProjectVariantsReadService

router = APIRouter()


@router.get("/api/projects/{project_id}/variants", response_model=ProjectVariantsResponse)
def project_variants(
    project_id: int,
    state: Literal["active", "orphan", "all"] = Query(default="active"),
    branch_ref: list[str] | None = Query(default=None),
    search_business_key: str | None = Query(default=None),
    search_source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> ProjectVariantsResponse:
    return handle_errors(
        lambda: ProjectVariantsResponse(
            **ProjectVariantsReadService().list_variants(
                project_id=project_id,
                state=state,
                branch_refs=[parse_branch_ref(item) for item in branch_ref or []],
                search_business_key=search_business_key,
                search_source=search_source,
                page=page,
                page_size=page_size,
            )
        )
    )


@router.get("/api/projects/{project_id}/entries/{business_key}/variants", response_model=EntryVariantsResponse)
def entry_variants(project_id: int, business_key: str) -> EntryVariantsResponse:
    return handle_errors(
        lambda: EntryVariantsResponse(
            **InspectionReadService().entry_variants(
                business_key,
                project_id=project_id,
            )
        )
    )


@router.get("/api/projects/{project_id}/orphan-variants", response_model=OrphanVariantsResponse)
def orphan_variants(project_id: int) -> OrphanVariantsResponse:
    return handle_errors(
        lambda: OrphanVariantsResponse(
            **InspectionReadService().orphan_variants(project_id=project_id)
        )
    )
