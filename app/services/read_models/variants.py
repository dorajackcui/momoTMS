from __future__ import annotations

import sqlite3
from typing import Any, Literal

from app.db import get_conn
from app.services.branch.models import BranchRef
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.hydration import ProjectVariantRowAssembler
from app.services.variant.pivot import pivot_changed_by_branch_ref as format_pivot_changed_by_branch_ref
from app.services.variant.bindings import BindingLookupService
from app.services.variant.repositories import VariantQueryRepository


ProjectVariantsState = Literal["active", "orphan", "all"]


class ProjectVariantsQueryRepository:
    def list_variant_rows(
        self,
        project_id: int,
        *,
        state: ProjectVariantsState,
        branch_refs: list[BranchRef],
        search_business_key: str | None,
        search_source: str | None,
        pivot_status: str | None,
        pivot_changed_by_branch_ref: BranchRef | None,
        page: int,
        page_size: int | None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        where_clauses = [
            "e.project_id = ?",
            "v.trashed_at IS NULL",
        ]
        params: list[Any] = [project_id]
        active_binding_exists = (
            "EXISTS (SELECT 1 FROM scope_bindings active_b WHERE active_b.variant_id = v.variant_id)"
        )

        if state == "active":
            where_clauses.append(active_binding_exists)
        elif state == "orphan":
            where_clauses.append(f"NOT {active_binding_exists}")

        normalized_business_key = (search_business_key or "").strip().lower()
        if normalized_business_key:
            where_clauses.append("LOWER(e.business_key) LIKE ?")
            params.append(f"%{normalized_business_key}%")

        normalized_source = (search_source or "").strip().lower()
        if normalized_source:
            where_clauses.append("LOWER(v.source) LIKE ?")
            params.append(f"%{normalized_source}%")

        if pivot_status is not None:
            where_clauses.append("v.pivot_status = ?")
            params.append(pivot_status)

        if pivot_changed_by_branch_ref is not None:
            owner_scope_type, owner_scope_value = pivot_changed_by_branch_ref.as_tuple()
            where_clauses.append(
                "v.pivot_changed_by_scope_type = ? AND v.pivot_changed_by_scope_value = ?"
            )
            params.extend([owner_scope_type, owner_scope_value])

        if branch_refs:
            branch_conditions: list[str] = []
            for branch_ref in branch_refs:
                scope_type, scope_value = branch_ref.as_tuple()
                branch_conditions.append("(b.scope_type = ? AND b.scope_value = ?)")
                params.extend([scope_type, scope_value])
            where_clauses.append(
                "EXISTS ("
                "SELECT 1 FROM scope_bindings b "
                "WHERE b.variant_id = v.variant_id "
                f"AND ({' OR '.join(branch_conditions)})"
                ")"
            )

        where_sql = " AND ".join(where_clauses)
        select_sql = f"""
            SELECT
                e.entry_id,
                e.project_id,
                e.business_key,
                v.variant_id,
                v.file_name,
                v.source,
                v.orphaned_at,
                v.trashed_at,
                v.trash_until,
                v.restored_at,
                v.pivot_status,
                v.pivot_changed_by_scope_type,
                v.pivot_changed_by_scope_value,
                v.pivot_changed_at,
                v.pivot_reviewed_at,
                v.pivot_status_updated_at,
                v.created_at,
                v.updated_at
            FROM variants v
            JOIN entries e ON e.entry_id = v.entry_id
            WHERE {where_sql}
            ORDER BY v.updated_at DESC, v.variant_id DESC
        """
        count_sql = f"""
            SELECT COUNT(*) AS count
            FROM variants v
            JOIN entries e ON e.entry_id = v.entry_id
            WHERE {where_sql}
        """

        page_value = max(page, 1)
        if page_size is None or page_size <= 0:
            offset = None
        else:
            offset = (page_value - 1) * page_size

        query_params = list(params)
        if offset is not None and page_size is not None:
            select_sql = f"{select_sql} LIMIT ? OFFSET ?"
            query_params.extend([page_size, offset])

        if conn is not None:
            total_rows = int(conn.execute(count_sql, params).fetchone()["count"])
            rows = conn.execute(select_sql, query_params).fetchall()
        else:
            with get_conn() as local_conn:
                total_rows = int(local_conn.execute(count_sql, params).fetchone()["count"])
                rows = local_conn.execute(select_sql, query_params).fetchall()

        page_size_value = page_size if page_size is not None and page_size > 0 else total_rows
        return {
            "rows": [dict(row) for row in rows],
            "total_rows": total_rows,
            "page": page_value if page_size is not None and page_size > 0 else 1,
            "page_size": page_size_value,
        }


class ProjectVariantsReadService:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.queries = ProjectVariantsQueryRepository()
        self.bindings = BindingLookupService()
        self.variant_queries = VariantQueryRepository()
        self.assembler = ProjectVariantRowAssembler()

    def list_variants(
        self,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
        state: ProjectVariantsState = "active",
        branch_refs: list[BranchRef] | None = None,
        search_business_key: str | None = None,
        search_source: str | None = None,
        pivot_status: str | None = None,
        pivot_changed_by_branch_ref: BranchRef | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        branch_filters = branch_refs or []
        payload = self.queries.list_variant_rows(
            project_id,
            state=state,
            branch_refs=branch_filters,
            search_business_key=search_business_key,
            search_source=search_source,
            pivot_status=pivot_status,
            pivot_changed_by_branch_ref=pivot_changed_by_branch_ref,
            page=page,
            page_size=page_size,
        )
        raw_rows = payload["rows"]
        if not raw_rows:
            return payload

        hydrated_variants = self.variant_queries.hydrate_variant_rows(raw_rows)
        variants_by_id = {
            int(variant["variant_id"]): variant
            for variant in hydrated_variants
        }
        bindings_by_entry = self.bindings.list_bindings_for_entries(
            sorted({int(row["entry_id"]) for row in raw_rows})
        )
        response_rows = []
        for row in raw_rows:
            variant_id = int(row["variant_id"])
            entry_id = int(row["entry_id"])
            variant = variants_by_id[variant_id]
            variant_bindings = [
                self.assembler.binding_summary(binding)
                for binding in bindings_by_entry.get(entry_id, [])
                if int(binding["variant_id"]) == variant_id
            ]
            variant_bindings.sort(key=lambda item: item["branch_ref"])
            state_value = "active" if variant_bindings else "orphan"
            response_rows.append(
                {
                    "variant_id": variant_id,
                    "entry_id": entry_id,
                    "business_key": row["business_key"],
                    "file_name": variant["file_name"],
                    "source": variant["source"],
                    "translations": variant["translations"],
                    "remarks": variant["remarks"],
                    "bindings": variant_bindings,
                    "state": state_value,
                    "orphaned_at": row["orphaned_at"] if state_value == "orphan" else None,
                    "pivot_status": variant["pivot_status"],
                    "pivot_changed_by_branch_ref": format_pivot_changed_by_branch_ref(variant),
                    "pivot_changed_at": variant["pivot_changed_at"],
                    "pivot_reviewed_at": variant["pivot_reviewed_at"],
                    "created_at": variant["created_at"],
                    "updated_at": variant["updated_at"],
                }
            )
        return {
            "rows": response_rows,
            "total_rows": payload["total_rows"],
            "page": payload["page"],
            "page_size": payload["page_size"],
        }
