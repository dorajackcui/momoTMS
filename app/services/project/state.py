from __future__ import annotations

from typing import Any

from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.jobs import JobService
from app.services.workflows.dev_versions import DevVersionService
from app.services.workflows.rel import RelService


class ProjectStateService:
    def __init__(self) -> None:
        self.project_service = ProjectService()
        self.rel_service = RelService()
        self.dev_version_service = DevVersionService()
        self.import_service = ImportService()
        self.job_service = JobService()

    def get_state(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        return {
            "project": self.project_service.require_project(project_id),
            "schema": self.project_service.get_schema(project_id),
            "rel_summary": self.rel_service.summary(project_id),
            "candidate_dev_version": self.dev_version_service.get_candidate_release(project_id),
            "dev_versions": self.dev_version_service.list_versions(project_id=project_id, active_only=True),
            "imports": self.import_service.list_batches(project_id=project_id),
            "jobs": self.job_service.list_jobs(project_id=project_id),
        }
