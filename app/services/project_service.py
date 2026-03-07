from __future__ import annotations

from typing import Any

from app.db import get_conn, json_loads

DEFAULT_PROJECT_ID = 1


class ProjectService:
    def get_default_project(self) -> dict[str, Any]:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT project_id, name, is_default, created_at
                FROM projects
                WHERE project_id = ?
                """,
                (DEFAULT_PROJECT_ID,),
            ).fetchone()
        if not row:
            raise KeyError("default project not found")
        return {
            "project_id": int(row["project_id"]),
            "name": row["name"],
            "is_default": bool(row["is_default"]),
            "created_at": row["created_at"],
        }

    def get_schema(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT schema_id, fixed_columns_json, translation_columns_json, remark_columns_json, created_at
                FROM project_schemas
                WHERE project_id = ?
                ORDER BY schema_id DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if not row:
            raise KeyError(f"schema not found for project: {project_id}")
        return {
            "schema_id": int(row["schema_id"]),
            "project_id": project_id,
            "fixed_columns": dict(json_loads(row["fixed_columns_json"])),
            "translation_columns": list(json_loads(row["translation_columns_json"])),
            "remark_columns": list(json_loads(row["remark_columns_json"])),
            "created_at": row["created_at"],
        }

    def resolve_headers(self, headers: list[Any], project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        schema = self.get_schema(project_id)
        normalized = {
            str(value).strip(): index + 1
            for index, value in enumerate(headers)
            if value is not None and str(value).strip()
        }
        fixed_columns = schema["fixed_columns"]
        for required_name in (fixed_columns["business_key"], fixed_columns["source"]):
            if required_name not in normalized:
                raise ValueError(f"workbook missing required header: {required_name}")
        translation_columns: dict[str, int] = {}
        for lang in schema["translation_columns"]:
            if lang not in normalized:
                raise ValueError(f"workbook missing translation column: {lang}")
            translation_columns[lang] = normalized[lang]
        remark_columns: dict[str, int] = {}
        for remark_key in schema["remark_columns"]:
            if remark_key not in normalized:
                raise ValueError(f"workbook missing remark column: {remark_key}")
            remark_columns[remark_key] = normalized[remark_key]
        return {
            "schema": schema,
            "file_name": normalized.get(fixed_columns["file_name"]),
            "business_key": normalized[fixed_columns["business_key"]],
            "source": normalized[fixed_columns["source"]],
            "translation_columns": translation_columns,
            "remark_columns": remark_columns,
        }

    def require_language(self, lang: str, project_id: int = DEFAULT_PROJECT_ID) -> None:
        schema = self.get_schema(project_id)
        if lang not in schema["translation_columns"]:
            raise ValueError(f"unsupported language column for project: {lang}")
