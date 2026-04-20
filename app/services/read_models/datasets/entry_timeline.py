from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.hydrate import ReadModelHydrator
from app.services.read_models.repository import ReadModelRepository


class EntryTimelineDataset:
    def __init__(
        self,
        *,
        projects: ProjectService | None = None,
        repository: ReadModelRepository | None = None,
        hydrator: ReadModelHydrator | None = None,
    ) -> None:
        self.projects = projects or ProjectService()
        self.repository = repository or ReadModelRepository()
        self.hydrator = hydrator or ReadModelHydrator()

    def get(
        self,
        business_key: str,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        payload = self.repository.get_entry_timeline(project_id, business_key)
        if payload is None:
            raise KeyError(f"entry not found: {business_key}")
        entry = payload["entry"]
        return {
            "project_id": int(entry["project_id"]),
            "entry_id": int(entry["entry_id"]),
            "business_key": entry["business_key"],
            "variants": self.hydrator.entry_timeline_items(payload["rows"]),
        }
