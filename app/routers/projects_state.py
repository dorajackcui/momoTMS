from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import CreateProjectRequest, ProjectSummary, StateResponse, StringDetail
from app.services.demo.service import DemoService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.variant.compatibility import StringService
from app.services.workflows.workbench import WorkbenchService
from app.routers.common import handle_errors

router = APIRouter()


@router.get("/api/state", response_model=StateResponse)
def state() -> StateResponse:
    return handle_errors(lambda: StateResponse(**WorkbenchService().get_state(DEFAULT_PROJECT_ID)))


@router.get("/api/projects", response_model=list[ProjectSummary])
def list_projects() -> list[ProjectSummary]:
    return [ProjectSummary(**item) for item in ProjectService().list_projects()]


@router.post("/api/projects", response_model=ProjectSummary)
def create_project(payload: CreateProjectRequest) -> ProjectSummary:
    return handle_errors(
        lambda: ProjectSummary(
            **ProjectService().create_project(
                payload.name,
                payload.translation_columns,
                payload.remark_columns,
            )
        )
    )


@router.get("/api/projects/{project_id}/state", response_model=StateResponse)
def project_state(project_id: int) -> StateResponse:
    return handle_errors(lambda: StateResponse(**WorkbenchService().get_state(project_id)))


@router.post("/api/demo/reset", response_model=StateResponse)
def demo_reset() -> StateResponse:
    def run() -> StateResponse:
        DemoService().reset()
        return StateResponse(**WorkbenchService().get_state())

    return handle_errors(run)


@router.get("/api/strings", response_model=list[StringDetail])
def list_strings(
    search: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> list[StringDetail]:
    strings = StringService().list_strings(search=search, include_deleted=include_deleted)
    return [StringDetail(**item) for item in strings]


@router.get("/api/strings/{business_key}", response_model=StringDetail)
def get_string(business_key: str) -> StringDetail:
    def run() -> StringDetail:
        item = StringService().get_string(business_key, include_deleted=True)
        if not item:
            raise KeyError(f"string not found: {business_key}")
        return StringDetail(**item)

    return handle_errors(run)
