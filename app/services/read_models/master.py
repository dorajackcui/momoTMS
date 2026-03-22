from __future__ import annotations

from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.read_models._support import ReadModelSupport


class MasterQueryReadService(ReadModelSupport):
    def master_entry(self, business_key: str, project_id: int = DEFAULT_PROJECT_ID) -> dict:
        return self._master_entry(business_key, project_id=project_id)

    def master_search(self, source: str, project_id: int = DEFAULT_PROJECT_ID) -> dict:
        return self._master_search(source, project_id=project_id)
