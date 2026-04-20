from __future__ import annotations

from typing import Any

from app.db import get_conn
from app.services.branch.models import BranchRef
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.datasets.scope_members import ScopeMembershipDataset
from app.services.read_models.selectors import ScopeSelector


class BranchCatalogView:
    def __init__(
        self,
        *,
        projects: ProjectService | None = None,
        scope_members: ScopeMembershipDataset | None = None,
    ) -> None:
        self.projects = projects or ProjectService()
        self.scope_members = scope_members or ScopeMembershipDataset()

    def release_summary(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        *,
        skip_project_check: bool = False,
    ) -> dict[str, Any]:
        if not skip_project_check:
            self.projects.require_project(project_id)
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS entry_count,
                    COALESCE((
                        SELECT group_concat(business_key, char(31))
                        FROM (
                            SELECT e2.business_key AS business_key
                            FROM scope_bindings b2
                            JOIN entries e2 ON e2.entry_id = b2.entry_id
                            JOIN variants v2 ON v2.variant_id = b2.variant_id
                            WHERE e2.project_id = ?
                              AND b2.scope_type = 'rel'
                              AND b2.scope_value = 'current'
                              AND v2.trashed_at IS NULL
                            ORDER BY e2.business_key
                            LIMIT 20
                        )
                    ), '') AS business_keys
                FROM scope_bindings b
                JOIN entries e ON e.entry_id = b.entry_id
                JOIN variants v ON v.variant_id = b.variant_id
                WHERE e.project_id = ?
                  AND b.scope_type = 'rel'
                  AND b.scope_value = 'current'
                  AND v.trashed_at IS NULL
                """,
                (project_id, project_id),
            ).fetchone()
        business_keys = [item for item in (row["business_keys"] or "").split(chr(31)) if item]
        return {
            "branch_ref": "rel/current",
            "entry_count": int(row["entry_count"] or 0),
            "business_keys": business_keys,
        }

    def list_dev_branches(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        *,
        active_only: bool = True,
        skip_project_check: bool = False,
    ) -> list[dict[str, Any]]:
        if not skip_project_check:
            self.projects.require_project(project_id)
        query = """
            SELECT
                d.version,
                d.version_line,
                d.is_candidate_release,
                d.created_at,
                d.promoted_at,
                COUNT(
                    DISTINCT CASE
                        WHEN e.entry_id IS NOT NULL AND v.trashed_at IS NULL THEN b.entry_id
                        ELSE NULL
                    END
                ) AS entry_count
            FROM dev_versions d
            LEFT JOIN scope_bindings b
                ON b.scope_type = 'dev'
               AND b.scope_value = d.version
            LEFT JOIN entries e
                ON e.entry_id = b.entry_id
               AND e.project_id = d.project_id
            LEFT JOIN variants v
                ON v.variant_id = b.variant_id
            WHERE d.project_id = ?
        """
        params: list[Any] = [project_id]
        if active_only:
            query += " AND d.promoted_at IS NULL"
        query += """
            GROUP BY d.project_id, d.version, d.version_line, d.is_candidate_release, d.created_at, d.promoted_at
            ORDER BY d.created_at DESC, d.version DESC
        """
        with get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "project_id": project_id,
                "version": row["version"],
                "version_series": row["version_line"],
                "branch_ref": str(self.dev_branch(row["version"])),
                "is_candidate_release": bool(row["is_candidate_release"]),
                "entry_count": int(row["entry_count"] or 0),
                "created_at": row["created_at"],
                "promoted_at": row["promoted_at"],
            }
            for row in rows
        ]

    def get_dev_branch(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        self.projects.require_project(project_id)
        for branch in self.list_dev_branches(project_id=project_id, active_only=False, skip_project_check=True):
            if branch["version"] == version:
                branch["entries"] = self.list_branch_entries(self.dev_branch(version), project_id=project_id)
                return branch
        raise KeyError(f"dev branch not found: {version}")

    def get_candidate_dev_branch(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        active_branches: list[dict[str, Any]] | None = None,
        skip_project_check: bool = False,
    ) -> dict[str, Any] | None:
        if not skip_project_check:
            self.projects.require_project(project_id)
        branches = (
            active_branches
            if active_branches is not None
            else self.list_dev_branches(project_id=project_id, skip_project_check=True)
        )
        for branch in branches:
            if branch["is_candidate_release"]:
                branch_detail = dict(branch)
                branch_detail["entries"] = self.list_branch_entries(self.dev_branch(branch["version"]), project_id=project_id)
                return branch_detail
        return None

    def list_branch_entries(
        self,
        branch_ref: BranchRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> list[dict[str, Any]]:
        self.projects.require_project(project_id)
        return self.scope_members.list_entry_views(
            ScopeSelector.from_branch(branch_ref),
            project_id=project_id,
        )

    def release_branch(self) -> BranchRef:
        return BranchRef.rel_current()

    def dev_branch(self, version: str) -> BranchRef:
        return BranchRef.dev(version)

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
