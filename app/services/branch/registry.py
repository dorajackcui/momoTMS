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
        mark_as_candidate: bool | None = None,
        project_id: int = DEFAULT_PROJECT_ID,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        version_series = derive_version_series(version)
        if conn is None:
            with get_conn() as local_conn:
                self.ensure_dev_branch(
                    version,
                    mark_as_candidate=mark_as_candidate,
                    project_id=project_id,
                    conn=local_conn,
                )
            return self.get_dev_branch_metadata(version, project_id)

        existing = conn.execute(
            """
            SELECT is_candidate_release
            FROM dev_versions
            WHERE project_id = ? AND version = ?
            LIMIT 1
            """,
            (project_id, version),
        ).fetchone()
        if mark_as_candidate is True:
            conn.execute(
                "UPDATE dev_versions SET is_candidate_release = 0 WHERE project_id = ?",
                (project_id,),
            )
        if existing is None:
            is_candidate_release = 1 if mark_as_candidate is True else 0
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
                """,
                (
                    project_id,
                    version,
                    version_series,
                    is_candidate_release,
                    now_iso(),
                ),
            )
        elif mark_as_candidate is not None:
            conn.execute(
                """
                UPDATE dev_versions
                SET version_line = ?, is_candidate_release = ?
                WHERE project_id = ? AND version = ?
                """,
                (version_series, 1 if mark_as_candidate else 0, project_id, version),
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
            SELECT is_candidate_release
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
            "is_candidate_release": bool(branch_row["is_candidate_release"]) if branch_row else False,
            "branch_ref": str(self.dev_branch(version)),
        }

    def get_dev_branch_metadata(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        self.projects.require_project(project_id)
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT
                    version,
                    version_line,
                    is_candidate_release,
                    created_at,
                    promoted_at
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
            "is_candidate_release": bool(row["is_candidate_release"]),
            "created_at": row["created_at"],
            "promoted_at": row["promoted_at"],
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
