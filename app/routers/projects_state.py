from __future__ import annotations

from fastapi import APIRouter

from app.routers.common import handle_errors
from app.schemas import CreateProjectRequest, ProductStateResponse, ProjectSummary
from app.services.demo.service import DemoService
from app.services.project.bootstrap import ProjectBootstrapService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService

router = APIRouter()


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


@router.get("/api/projects/{project_id}/state", response_model=ProductStateResponse)
def project_state(project_id: int) -> ProductStateResponse:
    return handle_errors(lambda: ProductStateResponse(**ProjectBootstrapService().get_state(project_id)))


@router.post("/api/demo/reset", response_model=ProductStateResponse)
def demo_reset() -> ProductStateResponse:
    def run() -> ProductStateResponse:
        DemoService().reset()
        return ProductStateResponse(**ProjectBootstrapService().get_state(DEFAULT_PROJECT_ID))

    return handle_errors(run)
