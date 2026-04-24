from __future__ import annotations

from fastapi import APIRouter, Query

from app.routers.common import handle_errors
from app.schemas import (
    BranchListResponse,
    BranchLookupResponse,
    BranchRowsResponse,
    SameSourceCandidatesResponse,
)
from app.services.branch.models import BranchRef
from app.services.read_models.datasets.history import ProjectHistoryDataset
from app.services.read_models.datasets.scope_members import ScopeMembershipDataset
from app.services.read_models.derived.branch_summary import BranchSummaryView
from app.services.read_models.selectors import ScopeSelector, VariantFilter

router = APIRouter()


def _scope_rows_payload(
    project_id: int,
    scope_selector: ScopeSelector,
    *,
    search_business_key: str | None = None,
    search_source: str | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> dict:
    return ScopeMembershipDataset().list(
        scope_selector,
        filters=VariantFilter(
            search_business_key=search_business_key,
            search_source=search_source,
        ),
        project_id=project_id,
        page=page,
        page_size=page_size,
    )


def _scope_lookup_payload(
    project_id: int,
    scope_selector: ScopeSelector,
    *,
    business_key: str | None = None,
    source: str | None = None,
) -> dict:
    return ScopeMembershipDataset().lookup(
        scope_selector,
        project_id=project_id,
        business_key=business_key,
        source=source,
    )


def _branch_selector(branch_ref: str) -> tuple[BranchRef, ScopeSelector]:
    parsed_branch_ref = BranchRef.parse(branch_ref)
    return parsed_branch_ref, ScopeSelector.from_branch(parsed_branch_ref)


@router.get("/api/projects/{project_id}/branches", response_model=BranchListResponse)
def project_branch_summary(project_id: int, lang: str | None = Query(default=None)) -> BranchListResponse:
    return handle_errors(lambda: BranchListResponse(**BranchSummaryView().build(project_id=project_id, lang=lang)))


@router.get("/api/projects/{project_id}/scopes/{scope_ref:path}/rows", response_model=BranchRowsResponse)
def project_scope_rows(
    project_id: int,
    scope_ref: str,
    search_business_key: str | None = Query(default=None),
    search_source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> BranchRowsResponse:
    def run() -> BranchRowsResponse:
        selector = ScopeSelector.parse(scope_ref)
        if not selector.is_master and not selector.is_orphan:
            raise ValueError(f"scope route only accepts master or orphan, got: {scope_ref}")
        payload = _scope_rows_payload(
            project_id,
            selector,
            search_business_key=search_business_key,
            search_source=search_source,
            page=page,
            page_size=page_size,
        )
        payload.pop("scope_ref")
        return BranchRowsResponse(branch_ref=str(selector), **payload)

    return handle_errors(run)


@router.get("/api/projects/{project_id}/scopes/{scope_ref:path}/lookup", response_model=BranchLookupResponse)
def project_scope_lookup(
    project_id: int,
    scope_ref: str,
    business_key: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> BranchLookupResponse:
    def run() -> BranchLookupResponse:
        selector = ScopeSelector.parse(scope_ref)
        if not selector.is_master and not selector.is_orphan:
            raise ValueError(f"scope route only accepts master or orphan, got: {scope_ref}")
        payload = _scope_lookup_payload(
            project_id,
            selector,
            business_key=business_key,
            source=source,
        )
        payload.pop("scope_ref")
        return BranchLookupResponse(branch_ref=str(selector), **payload)

    return handle_errors(run)


@router.get("/api/projects/{project_id}/branches/{branch_ref:path}/rows", response_model=BranchRowsResponse)
def project_branch_rows(
    project_id: int,
    branch_ref: str,
    search_business_key: str | None = Query(default=None),
    search_source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> BranchRowsResponse:
    def run() -> BranchRowsResponse:
        parsed_branch_ref, branch_selector = _branch_selector(branch_ref)
        payload = _scope_rows_payload(
            project_id,
            branch_selector,
            search_business_key=search_business_key,
            search_source=search_source,
            page=page,
            page_size=page_size,
        )
        payload.pop("scope_ref", None)
        return BranchRowsResponse(
            branch_ref=str(parsed_branch_ref),
            **payload,
        )

    return handle_errors(run)


@router.get("/api/projects/{project_id}/branches/{branch_ref:path}/lookup", response_model=BranchLookupResponse)
def project_branch_lookup(
    project_id: int,
    branch_ref: str,
    business_key: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> BranchLookupResponse:
    def run() -> BranchLookupResponse:
        parsed_branch_ref, branch_selector = _branch_selector(branch_ref)
        payload = _scope_lookup_payload(
            project_id,
            branch_selector,
            business_key=business_key,
            source=source,
        )
        payload.pop("scope_ref", None)
        return BranchLookupResponse(
            branch_ref=str(parsed_branch_ref),
            **payload,
        )

    return handle_errors(run)


@router.get("/api/projects/{project_id}/history/same-source-candidates", response_model=SameSourceCandidatesResponse)
def project_same_source_candidates(
    project_id: int,
    business_key: str = Query(...),
    source: str = Query(...),
) -> SameSourceCandidatesResponse:
    return handle_errors(
        lambda: SameSourceCandidatesResponse(
            **ProjectHistoryDataset().same_source_candidates(
                business_key,
                source,
                project_id=project_id,
            )
        )
    )



