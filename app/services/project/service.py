from __future__ import annotations

import sqlite3
from typing import Any

from app.db import get_conn, json_loads
from app.services.shared.io import normalize_non_content_value
from app.services.shared.utils import now_iso

DEFAULT_PROJECT_ID = 1


class ProjectService:
    FIXED_COLUMNS = {
        "file_name": "file_name",
        "business_key": "business_key",
        "source": "source",
    }

    def list_projects(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT project_id, name, is_default, created_at
                FROM projects
                ORDER BY is_default DESC, project_id ASC
                """
            ).fetchall()
        return [self._hydrate_project(row) for row in rows]

    def create_project(
        self,
        name: str,
        translation_columns: list[str],
        remark_columns: list[str],
    ) -> dict[str, Any]:
        normalized_name = normalize_non_content_value(name)
        if not normalized_name:
            raise ValueError("project name is required")
        normalized_translation_columns = self._normalize_schema_columns(
            translation_columns,
            field_label="translation_columns",
        )
        normalized_remark_columns = self._normalize_schema_columns(
            remark_columns,
            field_label="remark_columns",
        )
        overlap = set(normalized_translation_columns) & set(normalized_remark_columns)
        if overlap:
            raise ValueError(f"schema columns must be distinct across translations and remarks: {sorted(overlap)}")
        fixed_names = {self.FIXED_COLUMNS["business_key"], self.FIXED_COLUMNS["source"]}
        if fixed_names & set(normalized_translation_columns + normalized_remark_columns):
            raise ValueError("schema columns cannot reuse fixed business headers")

        created_at = now_iso()
        with get_conn() as conn:
            is_default = 0
            existing_default = conn.execute(
                "SELECT project_id FROM projects WHERE is_default = 1 LIMIT 1"
            ).fetchone()
            if not existing_default:
                is_default = 1
            try:
                cur = conn.execute(
                    """
                    INSERT INTO projects(name, is_default, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (normalized_name, is_default, created_at),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"project name already exists: {normalized_name}") from exc
            project_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO project_schemas(
                    project_id,
                    fixed_columns_json,
                    translation_columns_json,
                    remark_columns_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    _json_dumps(self.FIXED_COLUMNS),
                    _json_dumps(normalized_translation_columns),
                    _json_dumps(normalized_remark_columns),
                    created_at,
                ),
            )
        return self.get_project(project_id)

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
        return self._hydrate_project(row)

    def get_project(self, project_id: int) -> dict[str, Any]:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT project_id, name, is_default, created_at
                FROM projects
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
        if not row:
            raise KeyError(f"project not found: {project_id}")
        return self._hydrate_project(row)

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

    def preview_headers(self, headers: list[Any], project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        schema = self.get_schema(project_id)
        normalized, available_headers = self._normalize_headers(headers)
        fixed_columns = schema["fixed_columns"]
        suggested_mapping = {
            "file_name": "",
            "business_key": fixed_columns["business_key"] if fixed_columns["business_key"] in normalized else "",
            "source": fixed_columns["source"] if fixed_columns["source"] in normalized else "",
            "translation_columns": {
                lang: lang if lang in normalized else ""
                for lang in schema["translation_columns"]
            },
            "remark_columns": {
                remark_key: remark_key if remark_key in normalized else ""
                for remark_key in schema["remark_columns"]
            },
        }
        missing_targets: list[str] = []
        if not suggested_mapping["business_key"]:
            missing_targets.append("business_key")
        if not suggested_mapping["source"]:
            missing_targets.append("source")
        for lang, header_name in suggested_mapping["translation_columns"].items():
            if not header_name:
                missing_targets.append(f"translation:{lang}")
        for remark_key, header_name in suggested_mapping["remark_columns"].items():
            if not header_name:
                missing_targets.append(f"remark:{remark_key}")
        return {
            "schema": schema,
            "available_headers": available_headers,
            "suggested_mapping": suggested_mapping,
            "missing_targets": missing_targets,
            "auto_match_ready": not missing_targets,
        }

    def resolve_headers(
        self,
        headers: list[Any],
        project_id: int = DEFAULT_PROJECT_ID,
        override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        preview = self.preview_headers(headers, project_id)
        schema = preview["schema"]
        normalized, _ = self._normalize_headers(headers)
        fixed_columns = schema["fixed_columns"]
        override = override or {}

        def resolve_header_name(
            *,
            field_label: str,
            default_header: str,
            selected_header: Any,
            has_override: bool,
            required: bool,
        ) -> int | None:
            chosen = normalize_non_content_value(selected_header)
            if has_override:
                header_name = chosen
            else:
                header_name = chosen or default_header
            if not header_name:
                if required:
                    raise ValueError(f"workbook missing required header mapping: {field_label}")
                return None
            if header_name not in normalized:
                raise ValueError(f"workbook missing required header: {header_name}")
            return normalized[header_name]

        business_key_header = resolve_header_name(
            field_label="business_key",
            default_header=fixed_columns["business_key"],
            selected_header=override.get("business_key"),
            has_override="business_key" in override,
            required=True,
        )
        source_header = resolve_header_name(
            field_label="source",
            default_header=fixed_columns["source"],
            selected_header=override.get("source"),
            has_override="source" in override,
            required=True,
        )
        translation_columns: dict[str, int] = {}
        override_translation = override.get("translation_columns") or {}
        for lang in schema["translation_columns"]:
            translation_columns[lang] = resolve_header_name(
                field_label=f"translation:{lang}",
                default_header=lang,
                selected_header=override_translation.get(lang),
                has_override=lang in override_translation,
                required=True,
            )
        remark_columns: dict[str, int] = {}
        override_remark = override.get("remark_columns") or {}
        for remark_key in schema["remark_columns"]:
            remark_columns[remark_key] = resolve_header_name(
                field_label=f"remark:{remark_key}",
                default_header=remark_key,
                selected_header=override_remark.get(remark_key),
                has_override=remark_key in override_remark,
                required=True,
            )
        return {
            "schema": schema,
            "file_name": None,
            "business_key": business_key_header,
            "source": source_header,
            "translation_columns": translation_columns,
            "remark_columns": remark_columns,
        }

    def require_language(self, lang: str, project_id: int = DEFAULT_PROJECT_ID) -> None:
        schema = self.get_schema(project_id)
        if lang not in schema["translation_columns"]:
            raise ValueError(f"unsupported language column for project: {lang}")

    def require_project(self, project_id: int) -> dict[str, Any]:
        return self.get_project(project_id)

    def _normalize_headers(self, headers: list[Any]) -> tuple[dict[str, int], list[str]]:
        normalized: dict[str, int] = {}
        available_headers: list[str] = []
        for index, value in enumerate(headers):
            header_name = normalize_non_content_value(value)
            if not header_name:
                continue
            if header_name not in normalized:
                normalized[header_name] = index + 1
                available_headers.append(header_name)
        return normalized, available_headers

    def _hydrate_project(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "project_id": int(row["project_id"]),
            "name": row["name"],
            "is_default": bool(row["is_default"]),
            "created_at": row["created_at"],
        }

    def _normalize_schema_columns(self, values: list[str], *, field_label: str) -> list[str]:
        if not values:
            raise ValueError(f"{field_label} must contain at least one column")
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = normalize_non_content_value(value)
            if not item:
                raise ValueError(f"{field_label} contains a blank column name")
            if item in seen:
                raise ValueError(f"{field_label} contains duplicate column: {item}")
            seen.add(item)
            normalized.append(item)
        return normalized


def _json_dumps(payload: Any) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)
