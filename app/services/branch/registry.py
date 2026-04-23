from __future__ import annotations

import sqlite3
from typing import Any

from app.db import get_conn
from app.services.branch.models import BranchRef, derive_version_series
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.utils import now_iso


class BranchRegistryService:
    def __init__(self) -> None:
        self.projects = ProjectService()

    def release_branch(self) -> BranchRef:
        return BranchRef.rel_current()

    def dev_branch(self, version: str) -> BranchRef:
        return BranchRef.dev(version)

    def ensure_dev_branch(
        self,
        version: str,
        project_id: int = DEFAULT_PROJECT_ID,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        version_series = derive_version_series(version)
        if conn is None:
            with get_conn() as local_conn:
                self.ensure_dev_branch(
                    version,
                    project_id=project_id,
                    conn=local_conn,
                )
            return self.get_dev_branch_metadata(version, project_id)

        existing = conn.execute(
            """
            SELECT version
            FROM dev_versions
            WHERE project_id = ? AND version = ?
            LIMIT 1
            """,
            (project_id, version),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO dev_versions(
                    project_id,
                    version,
                    version_line,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    project_id,
                    version,
                    version_series,
                    now_iso(),
                ),
            )
        else:
            conn.execute(
                """
                UPDATE dev_versions
                SET version_line = ?
                WHERE project_id = ? AND version = ?
                """,
                (version_series, project_id, version),
            )
        branch_row = conn.execute(
            """
            SELECT version
            FROM dev_versions
            WHERE project_id = ? AND version = ?
            LIMIT 1
            """,
            (project_id, version),
        ).fetchone()
        return {
            "project_id": project_id,
            "version": version,
            "version_series": version_series,
            "branch_ref": str(self.dev_branch(version)),
        }

    def get_dev_branch_metadata(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        return self._get_dev_branch_metadata(version, project_id=project_id, conn=None)

    def require_not_bootstrapped(
        self,
        version: str,
        project_id: int = DEFAULT_PROJECT_ID,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        metadata = self._get_dev_branch_metadata(version, project_id=project_id, conn=conn)
        if metadata["bootstrapped_at"]:
            raise ValueError(f"dev branch already bootstrapped: {version}")
        return metadata

    def mark_bootstrapped(
        self,
        version: str,
        *,
        bootstrap_job_id: int,
        bootstrap_import_batch_id: int,
        project_id: int = DEFAULT_PROJECT_ID,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        if conn is None:
            with get_conn() as local_conn:
                return self.mark_bootstrapped(
                    version,
                    bootstrap_job_id=bootstrap_job_id,
                    bootstrap_import_batch_id=bootstrap_import_batch_id,
                    project_id=project_id,
                    conn=local_conn,
                )
        self.projects.require_project(project_id)
        marker = now_iso()
        cursor = conn.execute(
            """
            UPDATE dev_versions
            SET bootstrapped_at = ?,
                bootstrap_job_id = ?,
                bootstrap_import_batch_id = ?
            WHERE project_id = ? AND version = ? AND bootstrapped_at IS NULL
            """,
            (
                marker,
                bootstrap_job_id,
                bootstrap_import_batch_id,
                project_id,
                version,
            ),
        )
        if int(cursor.rowcount or 0) != 1:
            row = conn.execute(
                """
                SELECT bootstrapped_at
                FROM dev_versions
                WHERE project_id = ? AND version = ?
                LIMIT 1
                """,
                (project_id, version),
            ).fetchone()
            if row is None:
                raise KeyError(f"dev branch not found: {version}")
            if row["bootstrapped_at"]:
                raise ValueError(f"dev branch already bootstrapped: {version}")
            raise RuntimeError(f"failed to mark dev branch bootstrapped: {version}")
        return self._get_dev_branch_metadata(version, project_id=project_id, conn=conn)

    def _get_dev_branch_metadata(
        self,
        version: str,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        if conn is None:
            with get_conn() as local_conn:
                return self._get_dev_branch_metadata(version, project_id=project_id, conn=local_conn)
        row = conn.execute(
                """
                SELECT
                    version,
                    version_line,
                    created_at,
                    bootstrapped_at,
                    bootstrap_job_id,
                    bootstrap_import_batch_id
                FROM dev_versions
                WHERE project_id = ? AND version = ?
                LIMIT 1
                """,
                (project_id, version),
            ).fetchone()
        if row is None:
            raise KeyError(f"dev branch not found: {version}")
        return {
            "project_id": project_id,
            "version": row["version"],
            "version_series": row["version_line"],
            "created_at": row["created_at"],
            "bootstrap_state": "bootstrapped" if row["bootstrapped_at"] else "not_bootstrapped",
            "bootstrapped_at": row["bootstrapped_at"],
            "bootstrap_job_id": (
                int(row["bootstrap_job_id"]) if row["bootstrap_job_id"] is not None else None
            ),
            "bootstrap_import_batch_id": (
                int(row["bootstrap_import_batch_id"]) if row["bootstrap_import_batch_id"] is not None else None
            ),
            "branch_ref": str(self.dev_branch(row["version"])),
        }

    def versions_in_series(self, version_series: str, project_id: int = DEFAULT_PROJECT_ID) -> list[str]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT version
                FROM dev_versions
                WHERE project_id = ? AND version_line = ?
                ORDER BY created_at DESC
                """,
                (project_id, version_series),
            ).fetchall()
        return [row["version"] for row in rows]
