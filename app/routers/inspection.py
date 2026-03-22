from __future__ import annotations

from fastapi import APIRouter

from app.routers.common import handle_errors
from app.schemas import EntryVariantsResponse, OrphanVariantsResponse
from app.services.read_models.inspection import InspectionReadService

router = APIRouter()


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
