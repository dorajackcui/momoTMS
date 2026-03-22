from __future__ import annotations

from typing import Any

from app.services.branch.details import BranchDetailService
from app.services.branch.registry import BranchRegistryService
from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.jobs import JobService


class ProjectBootstrapService:
    def __init__(self) -> None:
        self.branch_details = BranchDetailService()
        self.branch_registry = BranchRegistryService()
        self.project_service = ProjectService()
        self.import_service = ImportService()
        self.job_service = JobService()

    def get_state(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        project = self.project_service.require_project(project_id)
        dev_branches = self.branch_registry.list_dev_branches(
            project_id=project_id,
            active_only=True,
            skip_project_check=True,
        )
        return {
            "project": project,
            "schema": self.project_service.get_schema(project_id),
            "release_summary": self.branch_registry.release_summary(project_id, skip_project_check=True),
            "candidate_dev_branch": self.branch_details.get_candidate_dev_branch(
                project_id,
                active_branches=dev_branches,
                skip_project_check=True,
            ),
            "dev_branches": dev_branches,
            "imports": self.import_service.list_batches(project_id=project_id),
            "jobs": self.job_service.list_jobs(project_id=project_id),
        }
