from __future__ import annotations

from typing import Any

from app.db import get_conn
from app.services.branch.models import ScopeRef
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.service import ReadModelService
from app.services.shared.utils import now_iso
from app.services.variant.services import EntryService, EntryVariantViewAssembler, ScopeBindingService, VariantCatalogService


class BranchService:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.read_models = ReadModelService()
        self.entries = EntryService()
        self.catalog = VariantCatalogService()
        self.bindings = ScopeBindingService()
        self.assembler = EntryVariantViewAssembler()

    def release_scope(self) -> ScopeRef:
        return ScopeRef.rel_current()

    def dev_scope(self, version: str) -> ScopeRef:
        return ScopeRef.dev(version)

    def release_summary(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        members = self.list_scope_entries(self.release_scope(), project_id)
        return {
            "scope_ref": str(self.release_scope()),
            "entry_count": len(members),
            "business_keys": [item["business_key"] for item in members[:20]],
        }

    def list_branches(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        lang: str | None = None,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        return self.read_models.branch_summary(project_id=project_id, lang=lang)

    def compare_branches(
        self,
        base_scope_ref: ScopeRef,
        target_scope_ref: ScopeRef,
        project_id: int = DEFAULT_PROJECT_ID,
        lang: str | None = None,
        search: str | None = None,
        states: list[str] | None = None,
        diff_categories: list[str] | None = None,
        priority_statuses: list[str] | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        return self.read_models.compare_branches(
            base_scope_ref,
            target_scope_ref,
            project_id=project_id,
            lang=lang,
            search=search,
            states=states,
            diff_categories=diff_categories,
            priority_statuses=priority_statuses,
            page=page,
            page_size=page_size,
        )

    def translation_queue(
        self,
        target_scope_ref: ScopeRef,
        project_id: int = DEFAULT_PROJECT_ID,
        lang: str | None = None,
        search: str | None = None,
        priority_statuses: list[str] | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        return self.read_models.translation_queue(
            target_scope_ref,
            project_id=project_id,
            lang=lang,
            search=search,
            priority_statuses=priority_statuses,
            page=page,
            page_size=page_size,
        )

    def master_entry(self, business_key: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        self.projects.require_project(project_id)
        return self.read_models.master_entry(business_key, project_id)

    def master_search(self, source: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        self.projects.require_project(project_id)
        return self.read_models.master_search(source, project_id)

    def ensure_dev_branch(
        self,
        version: str,
        mark_as_candidate: bool | None = None,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        version_line = self._version_line(version)
        with get_conn() as conn:
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
                        version_line,
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
                    (version_line, 1 if mark_as_candidate else 0, project_id, version),
                )
            else:
                conn.execute(
                    """
                    UPDATE dev_versions
                    SET version_line = ?
                    WHERE project_id = ? AND version = ?
                    """,
                    (version_line, project_id, version),
                )
        branch = self.get_dev_branch(version, project_id)
        return {
            "project_id": project_id,
            "version": version,
            "version_line": version_line,
            "is_candidate_release": branch["is_candidate_release"],
            "scope_ref": str(self.dev_scope(version)),
        }

    def list_dev_branches(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        self.projects.require_project(project_id)
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
        return [
            {
                "project_id": project_id,
                "version": row["version"],
                "version_line": row["version_line"],
                "scope_ref": str(self.dev_scope(row["version"])),
                "is_candidate_release": bool(row["is_candidate_release"]),
                "entry_count": self.bindings.count_scope(self.dev_scope(row["version"]), project_id),
                "created_at": row["created_at"],
                "promoted_at": row["promoted_at"],
            }
            for row in rows
        ]

    def get_dev_branch(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        self.projects.require_project(project_id)
        for branch in self.list_dev_branches(project_id=project_id, active_only=False):
            if branch["version"] == version:
                branch["entries"] = self.list_scope_entries(self.dev_scope(version), project_id)
                return branch
        raise KeyError(f"dev branch not found: {version}")

    def get_candidate_dev_branch(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any] | None:
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
        return self.get_dev_branch(row["version"], project_id)

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

    def list_scope_entries(
        self,
        scope_ref: ScopeRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> list[dict[str, Any]]:
        results = self.bindings.list_scope_entries(scope_ref, project_id)
        return [
            self.assembler.assemble(
                item,
                [
                    binding
                    for binding in self.bindings.list_bindings_for_entry(int(item["entry_id"]))
                    if int(binding["variant_id"]) == int(item["variant"]["variant_id"])
                ],
            )
            for item in results
        ]

    def _version_line(self, version: str) -> str:
        parts = version.split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}.x"
        return f"{version}.x"
