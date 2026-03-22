from __future__ import annotations

from fastapi import APIRouter, Query

from app.routers.common import handle_errors, parse_branch_ref
from app.schemas import BranchCompareResponse, BranchListResponse, BranchQueueResponse, MasterEntryResponse, MasterSearchResponse
from app.services.read_models.service import ReadModelService

router = APIRouter()


@router.get("/api/projects/{project_id}/branches", response_model=BranchListResponse)
def project_branch_summary(project_id: int, lang: str | None = Query(default=None)) -> BranchListResponse:
    return handle_errors(lambda: BranchListResponse(**ReadModelService().branch_summary(project_id=project_id, lang=lang)))


@router.get("/api/projects/{project_id}/branches/compare", response_model=BranchCompareResponse)
def project_branch_compare(
    project_id: int,
    base_branch_ref: str = Query(...),
    target_branch_ref: str = Query(...),
    lang: str | None = Query(default=None),
    search: str | None = Query(default=None),
    state: list[str] | None = Query(default=None),
    diff_category: list[str] | None = Query(default=None),
    priority_status: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> BranchCompareResponse:
    return handle_errors(
        lambda: BranchCompareResponse(
            **ReadModelService().compare_branches(
                parse_branch_ref(base_branch_ref),
                parse_branch_ref(target_branch_ref),
                project_id=project_id,
                lang=lang,
                search=search,
                states=state,
                diff_categories=diff_category,
                priority_statuses=priority_status,
                page=page,
                page_size=page_size,
            ),
        )
    )


@router.get("/api/projects/{project_id}/branches/queue", response_model=BranchQueueResponse)
def project_branch_queue(
    project_id: int,
    target_branch_ref: str = Query(...),
    lang: str | None = Query(default=None),
    search: str | None = Query(default=None),
    priority_status: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> BranchQueueResponse:
    return handle_errors(
        lambda: BranchQueueResponse(
            **ReadModelService().translation_queue(
                parse_branch_ref(target_branch_ref),
                project_id=project_id,
                lang=lang,
                search=search,
                priority_statuses=priority_status,
                page=page,
                page_size=page_size,
            ),
        )
    )


@router.get("/api/projects/{project_id}/branches/master/entries/{business_key}", response_model=MasterEntryResponse)
def project_master_entry(project_id: int, business_key: str) -> MasterEntryResponse:
    return handle_errors(lambda: MasterEntryResponse(**ReadModelService().master_entry(business_key, project_id)))


@router.get("/api/projects/{project_id}/branches/master/search", response_model=MasterSearchResponse)
def project_master_search(project_id: int, source: str = Query(...)) -> MasterSearchResponse:
    return handle_errors(lambda: MasterSearchResponse(**ReadModelService().master_search(source, project_id)))
