from __future__ import annotations

from typing import Any

from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.derived.branch_catalog import BranchCatalogView
from app.services.shared.jobs import JobService


class ProjectBootstrapService:
    def __init__(self) -> None:
        self.branch_catalog = BranchCatalogView()
        self.project_service = ProjectService()
        self.import_service = ImportService()
        self.job_service = JobService()

    def get_state(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        project = self.project_service.require_project(project_id)
        dev_branches = self.branch_catalog.list_dev_branches(
            project_id=project_id,
            skip_project_check=True,
        )
        return {
            "project": project,
            "schema": self.project_service.get_schema(project_id),
            "release_summary": self.branch_catalog.release_summary(project_id, skip_project_check=True),
            "dev_branches": dev_branches,
            "imports": self.import_service.list_batches(project_id=project_id),
            "jobs": self.job_service.list_jobs(project_id=project_id),
        }
