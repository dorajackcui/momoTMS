from __future__ import annotations

from typing import Any

from app.db import get_conn, json_loads
from app.services.project_service import DEFAULT_PROJECT_ID
from app.services.string_service import StringService
from app.services.utils import now_iso


class DevVersionService:
    def __init__(self) -> None:
        self.strings = StringService()

    def ensure_version(
        self,
        version: str,
        mark_as_candidate: bool,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        version_line = self._version_line(version)
        with get_conn() as conn:
            if mark_as_candidate:
                conn.execute(
                    "UPDATE dev_versions SET is_candidate_release = 0 WHERE project_id = ?",
                    (project_id,),
                )
            conn.execute(
                """
                INSERT INTO dev_versions(
                    project_id,
                    version,
                    version_line,
                    is_candidate_release,
                    created_at,
                    promoted_at
                )
                VALUES (?, ?, ?, ?, ?, NULL)
                ON CONFLICT(project_id, version)
                DO UPDATE SET
                    version_line = excluded.version_line,
                    is_candidate_release = excluded.is_candidate_release
                """,
                (
                    project_id,
                    version,
                    version_line,
                    1 if mark_as_candidate else 0,
                    now_iso(),
                ),
            )
        return {
            "project_id": project_id,
            "version": version,
            "version_line": version_line,
            "is_candidate_release": mark_as_candidate,
        }

    def import_batch(
        self,
        import_batch_id: int,
        version: str,
        mark_as_candidate: bool = True,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        version_info = self.ensure_version(version, mark_as_candidate, project_id)
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT import_row_id, file_path, sheet_name, row_index, payload_json
                FROM import_rows
                WHERE import_batch_id = ? AND status = 'ok'
                ORDER BY import_row_id
                """,
                (import_batch_id,),
            ).fetchall()

        counts = {
            "created_count": 0,
            "updated_canonical_count": 0,
            "tagged_only_count": 0,
            "protected_skipped_count": 0,
        }
        report_rows: list[dict[str, Any]] = []
        for row in rows:
            payload = json_loads(row["payload_json"])
            business_key = payload["business_key"]
            existing = self.strings.get_string(
                business_key,
                project_id=project_id,
                include_deleted=True,
            )
            if not existing:
                string_id = self.strings.create_string(
                    business_key=business_key,
                    file_name=payload.get("file_name"),
                    source=payload["source"],
                    translations=payload.get("translations", {}),
                    remarks=payload.get("remarks", {}),
                    project_id=project_id,
                )
                self.strings.ensure_membership(string_id, "dev", version)
                status = "CREATED"
                counts["created_count"] += 1
            else:
                string_id = int(existing["string_id"])
                in_rel = self.strings.has_membership(string_id, "rel", "current")
                differs = self._payload_differs(existing, payload)
                if in_rel:
                    self.strings.ensure_membership(string_id, "dev", version)
                    if differs:
                        status = "PROTECTED_SKIPPED"
                        counts["protected_skipped_count"] += 1
                    else:
                        status = "TAGGED_ONLY"
                        counts["tagged_only_count"] += 1
                else:
                    self.strings.update_canonical(
                        string_id=string_id,
                        file_name=payload.get("file_name"),
                        source=payload["source"],
                        translations=payload.get("translations", {}),
                        remarks=payload.get("remarks", {}),
                        restore_if_deleted=existing["deleted_at"] is not None,
                    )
                    self.strings.ensure_membership(string_id, "dev", version)
                    status = "UPDATED_CANONICAL"
                    counts["updated_canonical_count"] += 1
            report_rows.append(
                {
                    "business_key": business_key,
                    "file_path": row["file_path"],
                    "sheet_name": row["sheet_name"],
                    "row_index": int(row["row_index"]),
                    "status": status,
                }
            )

        summary = {
            "import_batch_id": import_batch_id,
            "version": version,
            "version_line": version_info["version_line"],
            "is_candidate_release": mark_as_candidate,
            **counts,
            "processed_count": len(report_rows),
        }
        return {"summary": summary, "report_rows": report_rows}

    def list_versions(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT version, version_line, is_candidate_release, created_at, promoted_at
            FROM dev_versions
            WHERE project_id = ?
        """
        params: list[Any] = [project_id]
        if active_only:
            query += " AND promoted_at IS NULL"
        query += " ORDER BY created_at DESC, version DESC"
        with get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "project_id": project_id,
                    "version": row["version"],
                    "version_line": row["version_line"],
                    "is_candidate_release": bool(row["is_candidate_release"]),
                    "member_count": self.strings.membership_count("dev", row["version"], project_id),
                    "created_at": row["created_at"],
                    "promoted_at": row["promoted_at"],
                }
            )
        return results

    def get_version(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        for version_info in self.list_versions(project_id=project_id, active_only=False):
            if version_info["version"] == version:
                version_info["members"] = self.strings.get_membership_strings("dev", version, project_id)
                return version_info
        raise KeyError(f"dev version not found: {version}")

    def get_candidate_release(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT version
                FROM dev_versions
                WHERE project_id = ? AND is_candidate_release = 1 AND promoted_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if not row:
            return None
        return self.get_version(row["version"], project_id)

    def versions_in_line(self, version_line: str, project_id: int = DEFAULT_PROJECT_ID) -> list[str]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT version
                FROM dev_versions
                WHERE project_id = ? AND version_line = ?
                ORDER BY created_at DESC
                """,
                (project_id, version_line),
            ).fetchall()
        return [row["version"] for row in rows]

    def mark_promoted(self, versions: list[str], project_id: int = DEFAULT_PROJECT_ID) -> None:
        if not versions:
            return
        placeholders = ", ".join("?" for _ in versions)
        with get_conn() as conn:
            conn.execute(
                f"""
                UPDATE dev_versions
                SET promoted_at = ?, is_candidate_release = 0
                WHERE project_id = ? AND version IN ({placeholders})
                """,
                [now_iso(), project_id, *versions],
            )

    def _version_line(self, version: str) -> str:
        parts = version.split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}.x"
        return f"{version}.x"

    def _payload_differs(self, existing: dict[str, Any], payload: dict[str, Any]) -> bool:
        if (existing.get("file_name") or None) != (payload.get("file_name") or None):
            return True
        if existing["source"] != payload["source"]:
            return True
        if dict(existing.get("translations", {})) != dict(payload.get("translations", {})):
            return True
        return dict(existing.get("remarks", {})) != dict(payload.get("remarks", {}))
