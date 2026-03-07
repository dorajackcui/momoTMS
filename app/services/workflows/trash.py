from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.variant.compatibility import StringService


class TrashService:
    def __init__(self) -> None:
        self.strings = StringService()

    def delete(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        result = self.strings.soft_delete(business_keys, project_id=project_id, trash_days=30)
        summary = {
            "deleted_count": len(result["deleted"]),
            "already_deleted_count": len(result["already_deleted"]),
            "missing_count": len(result["missing"]),
        }
        report_rows = [
            *[{"business_key": key, "status": "DELETED"} for key in result["deleted"]],
            *[{"business_key": key, "status": "ALREADY_DELETED"} for key in result["already_deleted"]],
            *[{"business_key": key, "status": "MISSING"} for key in result["missing"]],
        ]
        return {"summary": summary, "report_rows": report_rows}

    def restore(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        result = self.strings.restore(business_keys, project_id=project_id)
        summary = {
            "restored_count": len(result["restored"]),
            "not_deleted_count": len(result["not_deleted"]),
            "missing_count": len(result["missing"]),
        }
        report_rows = [
            *[{"business_key": key, "status": "RESTORED"} for key in result["restored"]],
            *[{"business_key": key, "status": "NOT_DELETED"} for key in result["not_deleted"]],
            *[{"business_key": key, "status": "MISSING"} for key in result["missing"]],
        ]
        return {"summary": summary, "report_rows": report_rows}
