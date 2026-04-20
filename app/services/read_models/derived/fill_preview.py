from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.read_models.datasets.history import ProjectHistoryDataset


class FillPreviewView:
    def __init__(self, *, history: ProjectHistoryDataset | None = None) -> None:
        self.history = history or ProjectHistoryDataset()

    def build(
        self,
        lang: str,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        rows = self.history.fill_candidates(lang, project_id=project_id)
        return {
            "lang": lang,
            "rows": rows,
            "total_rows": len(rows),
        }
