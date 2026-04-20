from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from app.routers.common import handle_errors, parse_branch_ref
from app.schemas import EntryVariantsResponse, OrphanVariantsResponse, ProjectVariantsResponse
from app.services.read_models.datasets.entry_timeline import EntryTimelineDataset
from app.services.read_models.datasets.live_variants import ProjectLiveVariantsDataset
from app.services.read_models.selectors import VariantFilter

router = APIRouter()


@router.get("/api/projects/{project_id}/variants", response_model=ProjectVariantsResponse)
def project_variants(
    project_id: int,
    state: Literal["active", "orphan", "all"] = Query(default="active"),
    branch_ref: list[str] | None = Query(default=None),
    search_business_key: str | None = Query(default=None),
    search_source: str | None = Query(default=None),
    pivot_status: Literal["init", "changed", "reviewed"] | None = Query(default=None),
    pivot_changed_by_branch_ref: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> ProjectVariantsResponse:
    return handle_errors(
        lambda: ProjectVariantsResponse(
            **ProjectLiveVariantsDataset().list(
                VariantFilter(
                    state=state,
                    branch_refs=tuple(parse_branch_ref(item) for item in branch_ref or []),
                    search_business_key=search_business_key,
                    search_source=search_source,
                    pivot_status=pivot_status,
                    pivot_changed_by_branch_ref=(
                        parse_branch_ref(pivot_changed_by_branch_ref)
                        if pivot_changed_by_branch_ref is not None
                        else None
                    ),
                ),
                project_id=project_id,
                page=page,
                page_size=page_size,
            )
        )
    )


@router.get("/api/projects/{project_id}/entries/{business_key}/variants", response_model=EntryVariantsResponse)
def entry_variants(project_id: int, business_key: str) -> EntryVariantsResponse:
    return handle_errors(
        lambda: EntryVariantsResponse(
            **EntryTimelineDataset().get(
                business_key,
                project_id=project_id,
            )
        )
    )


@router.get("/api/projects/{project_id}/orphan-variants", response_model=OrphanVariantsResponse)
def orphan_variants(project_id: int) -> OrphanVariantsResponse:
    def run() -> OrphanVariantsResponse:
        payload = ProjectLiveVariantsDataset().list(
            VariantFilter(state="orphan"),
            project_id=project_id,
        )
        return OrphanVariantsResponse(
            project_id=project_id,
            results=[
                {
                    "project_id": project_id,
                    "entry_id": row["entry_id"],
                    "business_key": row["business_key"],
                    "variant_id": row["variant_id"],
                    "file_name": row["file_name"],
                    "source": row["source"],
                    "translations": row["translations"],
                    "remarks": row["remarks"],
                    "orphaned_at": row["orphaned_at"] or "",
                    "updated_at": row["updated_at"],
                }
                for row in payload["rows"]
            ],
        )

    return handle_errors(run)
