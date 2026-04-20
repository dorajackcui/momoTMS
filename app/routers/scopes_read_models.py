from __future__ import annotations

from fastapi import APIRouter, Query

from app.routers.common import handle_errors
from app.schemas import (
    BranchListResponse,
    BranchLookupResponse,
    BranchRowsResponse,
    MasterEntryResponse,
    MasterQueryRow,
    MasterSearchResponse,
    SameSourceCandidatesResponse,
    ScopeLookupResponse,
    ScopeRowsResponse,
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


@router.get("/api/projects/{project_id}/scopes/{scope_ref:path}/rows", response_model=ScopeRowsResponse)
def project_scope_rows(
    project_id: int,
    scope_ref: str,
    search_business_key: str | None = Query(default=None),
    search_source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> ScopeRowsResponse:
    return handle_errors(
        lambda: ScopeRowsResponse(
            **_scope_rows_payload(
                project_id,
                ScopeSelector.parse(scope_ref),
                search_business_key=search_business_key,
                search_source=search_source,
                page=page,
                page_size=page_size,
            ),
        )
    )


@router.get("/api/projects/{project_id}/scopes/{scope_ref:path}/lookup", response_model=ScopeLookupResponse)
def project_scope_lookup(
    project_id: int,
    scope_ref: str,
    business_key: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> ScopeLookupResponse:
    return handle_errors(
        lambda: ScopeLookupResponse(
            **_scope_lookup_payload(
                project_id,
                ScopeSelector.parse(scope_ref),
                business_key=business_key,
                source=source,
            ),
        )
    )


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


@router.get("/api/projects/{project_id}/branches/master/entries/{business_key}", response_model=MasterEntryResponse)
def project_master_entry(project_id: int, business_key: str) -> MasterEntryResponse:
    def run() -> MasterEntryResponse:
        payload = ScopeMembershipDataset().lookup(
            ScopeSelector.master(),
            business_key=business_key,
            project_id=project_id,
        )
        if not payload["rows"]:
            raise KeyError(f"entry not found in master scope: {business_key}")
        results = [
            MasterQueryRow(
                business_key=row["business_key"],
                scope_ref="master",
                variant_id=row["variant_id"],
                file_name=row["file_name"],
                source=row["source"],
                translations=row["translations"],
                remarks=row["remarks"],
            )
            for row in payload["rows"]
        ]
        return MasterEntryResponse(
            business_key=business_key,
            entry_id=payload["rows"][0]["entry_id"],
            results=results,
        )

    return handle_errors(run)


@router.get("/api/projects/{project_id}/branches/master/search", response_model=MasterSearchResponse)
def project_master_search(project_id: int, source: str = Query(...)) -> MasterSearchResponse:
    def run() -> MasterSearchResponse:
        payload = ScopeMembershipDataset().lookup(
            ScopeSelector.master(),
            source=source,
            project_id=project_id,
        )
        results = [
            MasterQueryRow(
                business_key=row["business_key"],
                scope_ref="master",
                variant_id=row["variant_id"],
                file_name=row["file_name"],
                source=row["source"],
                translations=row["translations"],
                remarks=row["remarks"],
            )
            for row in payload["rows"]
        ]
        return MasterSearchResponse(source=source, results=results)

    return handle_errors(run)
