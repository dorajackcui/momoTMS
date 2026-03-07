from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import (
    BranchCompare,
    MasterEntryResult,
    MasterSearchResult,
    ScopeSummaryResponse,
    TranslationQueueResult,
)
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.read_models.service import ReadModelService
from app.routers.common import handle_errors, parse_scope_ref

router = APIRouter()


@router.get("/api/scopes/summary", response_model=ScopeSummaryResponse)
def scope_summary(lang: str | None = Query(default=None)) -> ScopeSummaryResponse:
    return handle_errors(lambda: ScopeSummaryResponse(**ReadModelService().scope_summary(project_id=DEFAULT_PROJECT_ID, lang=lang)))


@router.get("/api/projects/{project_id}/scopes/summary", response_model=ScopeSummaryResponse)
def project_scope_summary(project_id: int, lang: str | None = Query(default=None)) -> ScopeSummaryResponse:
    return handle_errors(lambda: ScopeSummaryResponse(**ReadModelService().scope_summary(project_id=project_id, lang=lang)))


@router.get("/api/scopes/compare", response_model=BranchCompare)
def scope_compare(
    base: str = Query(...),
    target: str = Query(...),
    lang: str | None = Query(default=None),
    search: str | None = Query(default=None),
    state: list[str] | None = Query(default=None),
    diff_category: list[str] | None = Query(default=None),
    priority_status: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> BranchCompare:
    return handle_errors(
        lambda: BranchCompare(
            **_compare_scopes_response(
                base=base,
                target=target,
                project_id=DEFAULT_PROJECT_ID,
                lang=lang,
                search=search,
                state=state,
                diff_category=diff_category,
                priority_status=priority_status,
                page=page,
                page_size=page_size,
            ),
        )
    )


@router.get("/api/projects/{project_id}/scopes/compare", response_model=BranchCompare)
def project_scope_compare(
    project_id: int,
    base: str = Query(...),
    target: str = Query(...),
    lang: str | None = Query(default=None),
    search: str | None = Query(default=None),
    state: list[str] | None = Query(default=None),
    diff_category: list[str] | None = Query(default=None),
    priority_status: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> BranchCompare:
    return handle_errors(
        lambda: BranchCompare(
            **_compare_scopes_response(
                base=base,
                target=target,
                project_id=project_id,
                lang=lang,
                search=search,
                state=state,
                diff_category=diff_category,
                priority_status=priority_status,
                page=page,
                page_size=page_size,
            ),
        )
    )


@router.get("/api/translation-queue", response_model=TranslationQueueResult)
def translation_queue(
    target: str = Query(...),
    lang: str | None = Query(default=None),
    search: str | None = Query(default=None),
    priority_status: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> TranslationQueueResult:
    return handle_errors(
        lambda: TranslationQueueResult(
            **_translation_queue_response(
                target=target,
                project_id=DEFAULT_PROJECT_ID,
                lang=lang,
                search=search,
                priority_status=priority_status,
                page=page,
                page_size=page_size,
            ),
        )
    )


@router.get("/api/projects/{project_id}/translation-queue", response_model=TranslationQueueResult)
def project_translation_queue(
    project_id: int,
    target: str = Query(...),
    lang: str | None = Query(default=None),
    search: str | None = Query(default=None),
    priority_status: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> TranslationQueueResult:
    return handle_errors(
        lambda: TranslationQueueResult(
            **_translation_queue_response(
                target=target,
                project_id=project_id,
                lang=lang,
                search=search,
                priority_status=priority_status,
                page=page,
                page_size=page_size,
            ),
        )
    )


@router.get("/api/master/entries/{business_key}", response_model=MasterEntryResult)
def master_entry(business_key: str) -> MasterEntryResult:
    return handle_errors(lambda: MasterEntryResult(**ReadModelService().master_entry(business_key, DEFAULT_PROJECT_ID)))


@router.get("/api/projects/{project_id}/master/entries/{business_key}", response_model=MasterEntryResult)
def project_master_entry(project_id: int, business_key: str) -> MasterEntryResult:
    return handle_errors(lambda: MasterEntryResult(**ReadModelService().master_entry(business_key, project_id)))


@router.get("/api/master/search", response_model=MasterSearchResult)
def master_search(source: str = Query(...)) -> MasterSearchResult:
    return handle_errors(lambda: MasterSearchResult(**ReadModelService().master_search(source, DEFAULT_PROJECT_ID)))


@router.get("/api/projects/{project_id}/master/search", response_model=MasterSearchResult)
def project_master_search(project_id: int, source: str = Query(...)) -> MasterSearchResult:
    return handle_errors(lambda: MasterSearchResult(**ReadModelService().master_search(source, project_id)))


def _compare_scopes_response(
    *,
    base: str,
    target: str,
    project_id: int,
    lang: str | None,
    search: str | None,
    state: list[str] | None,
    diff_category: list[str] | None,
    priority_status: list[str] | None,
    page: int,
    page_size: int | None,
) -> dict:
    base_type, base_value = parse_scope_ref(base)
    target_type, target_value = parse_scope_ref(target)
    return ReadModelService().compare_scopes(
        base_type,
        base_value,
        target_type,
        target_value,
        project_id=project_id,
        lang=lang,
        search=search,
        states=state,
        diff_categories=diff_category,
        priority_statuses=priority_status,
        page=page,
        page_size=page_size,
    )


def _translation_queue_response(
    *,
    target: str,
    project_id: int,
    lang: str | None,
    search: str | None,
    priority_status: list[str] | None,
    page: int,
    page_size: int | None,
) -> dict:
    target_type, target_value = parse_scope_ref(target)
    return ReadModelService().translation_queue(
        target_type,
        target_value,
        project_id=project_id,
        lang=lang,
        search=search,
        priority_statuses=priority_status,
        page=page,
        page_size=page_size,
    )
