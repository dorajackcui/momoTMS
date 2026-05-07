from __future__ import annotations

import sqlite3
from typing import Any

from app.db import get_conn
from app.schemas import VariantGridColumnRef
from app.services.branch.models import BranchRef
from app.services.read_models.grid_filters import (
    GridColumnFilter,
    GridOptionsSpec,
    GridQuerySpec,
    filters_excluding_target,
)
from app.services.read_models.selectors import ScopeSelector, VariantFilter
from app.services.read_models.types import FillCandidate, ProjectionRow
from app.services.shared.io import normalize_content_value, normalize_non_content_value


class ReadModelRepository:
    def select_branch_identity_rows(
        self,
        project_id: int,
        scope_selector: ScopeSelector,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        if scope_selector.is_master or scope_selector.is_orphan or scope_selector.branch_ref is None:
            raise ValueError("branch scope selector is required")
        scope_type, scope_value = scope_selector.branch_ref.as_tuple()
        query = """
            SELECT
                e.entry_id,
                e.business_key,
                b.variant_id
            FROM scope_bindings b
            JOIN entries e ON e.entry_id = b.entry_id
            JOIN variants v ON v.variant_id = b.variant_id
            WHERE e.project_id = ?
              AND b.scope_type = ?
              AND b.scope_value = ?
              AND v.trashed_at IS NULL
            ORDER BY LOWER(e.business_key)
        """
        params = (project_id, scope_type, scope_value)
        if conn is not None:
            rows = conn.execute(query, params).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(query, params).fetchall()
        return [
            {
                "entry_id": int(row["entry_id"]),
                "business_key": normalize_non_content_value(row["business_key"]),
                "variant_id": int(row["variant_id"]),
            }
            for row in rows
        ]

    def select_scope_member_rows(
        self,
        project_id: int,
        scope_selector: ScopeSelector,
        *,
        search_business_key: str | None = None,
        search_source: str | None = None,
        business_key: str | None = None,
        source: str | None = None,
        page: int = 1,
        page_size: int | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        where_clauses, params = self._scope_member_where(
            project_id,
            scope_selector,
            search_business_key=search_business_key,
            search_source=search_source,
            business_key=business_key,
            source=source,
        )
        return self._select_variant_rows(
            where_clauses,
            params,
            page=page,
            page_size=page_size,
            order_sql="ORDER BY LOWER(e.business_key), v.updated_at DESC, v.variant_id DESC",
            conn=conn,
        )

    def count_scope_members(
        self,
        project_id: int,
        scope_selector: ScopeSelector,
        *,
        search_business_key: str | None = None,
        search_source: str | None = None,
        business_key: str | None = None,
        source: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        where_clauses, params = self._scope_member_where(
            project_id,
            scope_selector,
            search_business_key=search_business_key,
            search_source=search_source,
            business_key=business_key,
            source=source,
        )
        return self._count_variant_rows(where_clauses, params, conn=conn)

    def list_live_variant_rows(
        self,
        project_id: int,
        filters: VariantFilter,
        *,
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
        if filters.state == "active":
            where_clauses.append(active_binding_exists)
        elif filters.state == "orphan":
            where_clauses.append(f"NOT {active_binding_exists}")

        if filters.normalized_business_key:
            where_clauses.append("LOWER(e.business_key) LIKE ?")
            params.append(f"%{filters.normalized_business_key}%")

        if filters.normalized_source:
            where_clauses.append("LOWER(v.source) LIKE ?")
            params.append(f"%{filters.normalized_source}%")

        if filters.pivot_status is not None:
            where_clauses.append("v.pivot_status = ?")
            params.append(filters.pivot_status)

        if filters.pivot_changed_by_branch_ref is not None:
            scope_type, scope_value = filters.pivot_changed_by_branch_ref.as_tuple()
            where_clauses.append(
                "v.pivot_changed_by_scope_type = ? AND v.pivot_changed_by_scope_value = ?"
            )
            params.extend([scope_type, scope_value])

        if filters.branch_refs:
            branch_conditions: list[str] = []
            for branch_ref in filters.branch_refs:
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

        rows = self._select_variant_rows(
            where_clauses,
            params,
            page=page,
            page_size=page_size,
            order_sql="ORDER BY v.updated_at DESC, v.variant_id DESC",
            conn=conn,
        )
        total_rows = self._count_variant_rows(where_clauses, params, conn=conn)
        page_size_value = page_size if page_size is not None and page_size > 0 else total_rows
        return {
            "rows": rows,
            "total_rows": total_rows,
            "page": max(page, 1) if page_size is not None and page_size > 0 else 1,
            "page_size": page_size_value,
        }

    def list_grid_variant_rows(
        self,
        spec: GridQuerySpec,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        where_clauses, params = self._grid_where(spec)
        rows = self._select_variant_rows(
            where_clauses,
            params,
            page=spec.page,
            page_size=spec.page_size,
            order_sql=self._grid_order_sql(spec),
            conn=conn,
        )
        total_rows = self._count_variant_rows(where_clauses, params, conn=conn)
        return {
            "rows": rows,
            "total_rows": total_rows,
            "page": spec.page,
            "page_size": spec.page_size,
            "has_next_page": spec.page * spec.page_size < total_rows,
            "total_rows_exact": True,
        }

    def list_grid_filter_options(
        self,
        spec: GridOptionsSpec,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        query_spec = GridQuerySpec(
            project_id=spec.query.project_id,
            scope_selector=spec.query.scope_selector,
            state=spec.query.state,
            filters=filters_excluding_target(spec.query.filters, spec.target_column),
            page=1,
            page_size=spec.limit,
        )
        where_clauses, where_params = self._grid_where(query_spec)
        join_sql = self._grid_option_join_sql(spec.target_column)
        value_sql, option_params = self._grid_option_value_sql(spec.target_column)
        if spec.option_search:
            where_clauses.append(f"LOWER(COALESCE({value_sql}, '')) LIKE ?")
            where_params.append(f"%{spec.option_search}%")
        where_sql = " AND ".join(where_clauses)
        query = f"""
            SELECT DISTINCT {value_sql} AS option_value
            FROM variants v
            JOIN entries e ON e.entry_id = v.entry_id
            {join_sql}
            WHERE {where_sql}
            ORDER BY
                CASE WHEN option_value IS NULL THEN 0 ELSE 1 END,
                LOWER(option_value)
            LIMIT ?
        """
        params = [*option_params, *where_params, spec.limit + 1]
        if conn is not None:
            rows = conn.execute(query, params).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(query, params).fetchall()
        values = [
            {
                "value": row["option_value"],
                "label": "(blank)" if row["option_value"] is None else row["option_value"],
                "count": None,
            }
            for row in rows[: spec.limit]
        ]
        return {
            "values": values,
            "limit": spec.limit,
            "has_more": len(rows) > spec.limit,
        }

    def list_same_source_history_rows(
        self,
        project_id: int,
        business_key: str,
        source: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                e.entry_id,
                e.project_id,
                e.business_key,
                v.variant_id,
                v.file_name,
                v.source,
                v.orphaned_at,
                v.trashed_at,
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
            WHERE e.project_id = ?
              AND e.business_key = ?
              AND v.source = ?
              AND v.trashed_at IS NULL
            ORDER BY
                v.updated_at DESC,
                v.variant_id DESC
        """
        params = (
            project_id,
            normalize_non_content_value(business_key),
            normalize_non_content_value(source),
        )
        if conn is not None:
            rows = conn.execute(query, params).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_fill_candidate_rows(
        self,
        project_id: int,
        lang: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[FillCandidate]:
        query = """
            SELECT
                e.business_key,
                v.source,
                v.variant_id,
                v.orphaned_at,
                v.updated_at,
                vt.target_text
            FROM variants v
            JOIN entries e ON e.entry_id = v.entry_id
            LEFT JOIN variant_translations vt
                ON vt.variant_id = v.variant_id
               AND vt.lang = ?
            WHERE e.project_id = ?
              AND v.trashed_at IS NULL
            ORDER BY
                e.business_key,
                v.source,
                v.updated_at DESC,
                v.variant_id DESC
        """
        params = (normalize_non_content_value(lang), project_id)
        if conn is not None:
            rows = conn.execute(query, params).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(query, params).fetchall()
        return [
            {
                "business_key": normalize_non_content_value(row["business_key"]),
                "source": normalize_non_content_value(row["source"]),
                "target_text": normalize_content_value(row["target_text"]),
                "variant_id": int(row["variant_id"]),
                "orphaned_at": row["orphaned_at"],
                "trashed_at": None,
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def get_entry_timeline(
        self,
        project_id: int,
        business_key: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        normalized_key = normalize_non_content_value(business_key)
        entry_query = """
            SELECT entry_id, project_id, business_key
            FROM entries
            WHERE project_id = ? AND business_key = ?
            LIMIT 1
        """
        variants_query = """
            SELECT
                e.entry_id,
                e.project_id,
                e.business_key,
                v.variant_id,
                v.file_name,
                v.source,
                v.orphaned_at,
                v.trashed_at,
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
            WHERE e.project_id = ? AND e.business_key = ?
              AND v.trashed_at IS NULL
            ORDER BY v.variant_id
        """
        params = (project_id, normalized_key)
        if conn is not None:
            entry = conn.execute(entry_query, params).fetchone()
            rows = conn.execute(variants_query, params).fetchall()
        else:
            with get_conn() as local_conn:
                entry = local_conn.execute(entry_query, params).fetchone()
                rows = local_conn.execute(variants_query, params).fetchall()
        if entry is None:
            return None
        return {
            "entry": {
                "entry_id": int(entry["entry_id"]),
                "project_id": int(entry["project_id"]),
                "business_key": normalize_non_content_value(entry["business_key"]),
            },
            "rows": [dict(row) for row in rows],
        }

    def list_active_branch_projections(
        self,
        project_id: int,
        *,
        lang: str | None = None,
    ) -> list[ProjectionRow]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                WITH branches AS (
                    SELECT
                        'rel' AS scope_type,
                        'current' AS scope_value,
                        NULL AS version_series
                    UNION ALL
                    SELECT
                        'dev' AS scope_type,
                        version AS scope_value,
                        version_line AS version_series
                    FROM dev_versions
                    WHERE project_id = ?
                )
                SELECT
                    br.scope_type,
                    br.scope_value,
                    br.version_series,
                    e.entry_id,
                    e.project_id,
                    e.business_key,
                    v.variant_id,
                    COALESCE(v.file_name, '') AS file_name,
                    COALESCE(v.source, '') AS source,
                    COALESCE((
                        SELECT target_text
                        FROM variant_translations vt
                        WHERE vt.variant_id = v.variant_id AND vt.lang = ?
                        LIMIT 1
                    ), '') AS lang_target_text,
                    COALESCE((
                        SELECT group_concat(piece, char(31))
                        FROM (
                            SELECT vt.lang || '=' || COALESCE(vt.target_text, '') AS piece
                            FROM variant_translations vt
                            WHERE vt.variant_id = v.variant_id
                            ORDER BY vt.lang
                        )
                    ), '') AS translations_fingerprint,
                    COALESCE((
                        SELECT group_concat(piece, char(31))
                        FROM (
                            SELECT vr.remark_key || '=' || COALESCE(vr.remark_value, '') AS piece
                            FROM variant_remarks vr
                            WHERE vr.variant_id = v.variant_id
                            ORDER BY vr.remark_key
                        )
                    ), '') AS remarks_fingerprint
                FROM branches br
                LEFT JOIN scope_bindings b
                    ON b.scope_type = br.scope_type
                   AND b.scope_value = br.scope_value
                LEFT JOIN entries e
                    ON e.entry_id = b.entry_id
                   AND e.project_id = ?
                LEFT JOIN variants v
                    ON v.variant_id = b.variant_id
                   AND v.trashed_at IS NULL
                ORDER BY
                    CASE WHEN br.scope_type = 'rel' THEN 0 ELSE 1 END,
                    br.scope_value,
                    e.business_key
                """,
                (project_id, lang, project_id),
            ).fetchall()
        return [
            {
                "branch_ref": f"{row['scope_type']}/{row['scope_value']}",
                "scope_type": row["scope_type"],
                "scope_value": row["scope_value"],
                "version_series": row["version_series"],
                "entry_id": int(row["entry_id"]) if row["entry_id"] is not None else None,
                "project_id": int(row["project_id"]) if row["project_id"] is not None else project_id,
                "business_key": (
                    normalize_non_content_value(row["business_key"])
                    if row["business_key"] is not None
                    else ""
                ),
                "variant_id": int(row["variant_id"]) if row["variant_id"] is not None else None,
                "file_name": normalize_non_content_value(row["file_name"]),
                "source": normalize_non_content_value(row["source"]),
                "lang_target_text": normalize_content_value(row["lang_target_text"]),
                "translations_fingerprint": row["translations_fingerprint"],
                "remarks_fingerprint": row["remarks_fingerprint"],
            }
            for row in rows
        ]

    def _scope_member_where(
        self,
        project_id: int,
        scope_selector: ScopeSelector,
        *,
        search_business_key: str | None = None,
        search_source: str | None = None,
        business_key: str | None = None,
        source: str | None = None,
    ) -> tuple[list[str], list[Any]]:
        where_clauses = [
            "e.project_id = ?",
            "v.trashed_at IS NULL",
        ]
        params: list[Any] = [project_id]
        if scope_selector.is_orphan:
            where_clauses.append(
                "NOT EXISTS ("
                "SELECT 1 FROM scope_bindings b "
                "WHERE b.variant_id = v.variant_id"
                ")"
            )
        elif not scope_selector.is_master:
            branch_ref = scope_selector.branch_ref
            if branch_ref is None:
                raise ValueError("branch scope selector is required")
            scope_type, scope_value = branch_ref.as_tuple()
            where_clauses.append(
                "EXISTS ("
                "SELECT 1 FROM scope_bindings b "
                "WHERE b.variant_id = v.variant_id "
                "AND b.scope_type = ? "
                "AND b.scope_value = ?"
                ")"
            )
            params.extend([scope_type, scope_value])

        normalized_business_key = normalize_non_content_value(business_key)
        if normalized_business_key:
            where_clauses.append("e.business_key = ?")
            params.append(normalized_business_key)

        normalized_source = normalize_non_content_value(source)
        if normalized_source:
            where_clauses.append("v.source = ?")
            params.append(normalized_source)

        search_key = normalize_non_content_value(search_business_key).lower()
        if search_key:
            where_clauses.append("LOWER(e.business_key) LIKE ?")
            params.append(f"%{search_key}%")

        search_value = normalize_non_content_value(search_source).lower()
        if search_value:
            where_clauses.append("LOWER(v.source) LIKE ?")
            params.append(f"%{search_value}%")
        return where_clauses, params

    def _grid_where(self, spec: GridQuerySpec) -> tuple[list[str], list[Any]]:
        where_clauses = [
            "e.project_id = ?",
            "v.trashed_at IS NULL",
        ]
        params: list[Any] = [spec.project_id]
        active_binding_exists = (
            "EXISTS (SELECT 1 FROM scope_bindings active_b WHERE active_b.variant_id = v.variant_id)"
        )

        if spec.scope_selector is None:
            if spec.state == "active":
                where_clauses.append(active_binding_exists)
            elif spec.state == "orphan":
                where_clauses.append(f"NOT {active_binding_exists}")
        else:
            branch_ref = spec.scope_selector.branch_ref
            if branch_ref is None:
                raise ValueError("branch scope selector is required")
            scope_type, scope_value = branch_ref.as_tuple()
            where_clauses.append(
                "EXISTS ("
                "SELECT 1 FROM scope_bindings scope_b "
                "WHERE scope_b.variant_id = v.variant_id "
                "AND scope_b.scope_type = ? "
                "AND scope_b.scope_value = ?"
                ")"
            )
            params.extend([scope_type, scope_value])

        for item in spec.filters:
            clause, clause_params = self._apply_grid_filter(item)
            if clause:
                where_clauses.append(clause)
                params.extend(clause_params)
        return where_clauses, params

    def _apply_grid_filter(self, item: GridColumnFilter) -> tuple[str | None, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        text_clause, text_params = self._grid_text_clause(item.column, item.text)
        if text_clause:
            clauses.append(text_clause)
            params.extend(text_params)
        values_clause, values_params = self._grid_values_clause(item.column, item.values)
        if values_clause:
            clauses.append(values_clause)
            params.extend(values_params)
        if not clauses:
            return None, []
        return f"({' AND '.join(clauses)})", params

    def _grid_field_expression(self, column: VariantGridColumnRef) -> str:
        if column.name == "business_key":
            return "e.business_key"
        if column.name == "file_name":
            return "v.file_name"
        if column.name == "source":
            return "v.source"
        if column.name == "pivot_status":
            return "v.pivot_status"
        if column.name == "state":
            return (
                "CASE WHEN EXISTS ("
                "SELECT 1 FROM scope_bindings state_b "
                "WHERE state_b.variant_id = v.variant_id"
                ") THEN 'active' ELSE 'orphan' END"
            )
        raise ValueError(f"unsupported grid field: {column.name}")

    def _grid_option_join_sql(self, column: VariantGridColumnRef) -> str:
        if column.kind == "field":
            if column.name == "branch":
                return "LEFT JOIN scope_bindings option_b ON option_b.variant_id = v.variant_id"
            return ""
        if column.kind == "translation":
            return (
                "LEFT JOIN variant_translations option_vt "
                "ON option_vt.variant_id = v.variant_id "
                "AND option_vt.lang = ?"
            )
        if column.kind == "remark":
            return (
                "LEFT JOIN variant_remarks option_vr "
                "ON option_vr.variant_id = v.variant_id "
                "AND option_vr.remark_key = ?"
            )
        raise ValueError(f"unsupported grid column kind: {column.kind}")

    def _grid_option_value_sql(self, column: VariantGridColumnRef) -> tuple[str, list[Any]]:
        if column.kind == "field":
            if column.name == "branch":
                return "NULLIF(COALESCE(option_b.scope_type || '/' || option_b.scope_value, ''), '')", []
            expression = self._grid_field_expression(column)
            return f"NULLIF(COALESCE({expression}, ''), '')", []
        if column.kind == "translation":
            return "NULLIF(COALESCE(option_vt.target_text, ''), '')", [column.name]
        if column.kind == "remark":
            return "NULLIF(COALESCE(option_vr.remark_value, ''), '')", [column.name]
        raise ValueError(f"unsupported grid column kind: {column.kind}")

    def _grid_text_clause(
        self,
        column: VariantGridColumnRef,
        text: str,
    ) -> tuple[str | None, list[Any]]:
        if not text:
            return None, []
        pattern = f"%{text}%"
        if column.kind == "field":
            if column.name == "branch":
                return (
                    "EXISTS ("
                    "SELECT 1 FROM scope_bindings branch_text_b "
                    "WHERE branch_text_b.variant_id = v.variant_id "
                    "AND LOWER(branch_text_b.scope_type || '/' || branch_text_b.scope_value) LIKE ?"
                    ")",
                    [pattern],
                )
            expression = self._grid_field_expression(column)
            return f"LOWER(COALESCE({expression}, '')) LIKE ?", [pattern]
        if column.kind == "translation":
            return (
                "EXISTS ("
                "SELECT 1 FROM variant_translations text_vt "
                "WHERE text_vt.variant_id = v.variant_id "
                "AND text_vt.lang = ? "
                "AND LOWER(COALESCE(text_vt.target_text, '')) LIKE ?"
                ")",
                [column.name, pattern],
            )
        if column.kind == "remark":
            return (
                "EXISTS ("
                "SELECT 1 FROM variant_remarks text_vr "
                "WHERE text_vr.variant_id = v.variant_id "
                "AND text_vr.remark_key = ? "
                "AND LOWER(COALESCE(text_vr.remark_value, '')) LIKE ?"
                ")",
                [column.name, pattern],
            )
        return None, []

    def _grid_values_clause(
        self,
        column: VariantGridColumnRef,
        values: tuple[str | None, ...],
    ) -> tuple[str | None, list[Any]]:
        if not values:
            return None, []
        non_blank_values = [value for value in values if value is not None]
        include_blank = any(value is None for value in values)
        clauses: list[str] = []
        params: list[Any] = []

        if column.kind == "field":
            if column.name == "branch":
                if non_blank_values:
                    branch_clauses: list[str] = []
                    for value in non_blank_values:
                        scope_type, scope_value = BranchRef.parse(value).as_tuple()
                        branch_clauses.append(
                            "(branch_value_b.scope_type = ? AND branch_value_b.scope_value = ?)"
                        )
                        params.extend([scope_type, scope_value])
                    clauses.append(
                        "EXISTS ("
                        "SELECT 1 FROM scope_bindings branch_value_b "
                        "WHERE branch_value_b.variant_id = v.variant_id "
                        f"AND ({' OR '.join(branch_clauses)})"
                        ")"
                    )
                if include_blank:
                    clauses.append(
                        "NOT EXISTS ("
                        "SELECT 1 FROM scope_bindings branch_blank_b "
                        "WHERE branch_blank_b.variant_id = v.variant_id"
                        ")"
                    )
            else:
                expression = self._grid_field_expression(column)
                value_clauses: list[str] = []
                if non_blank_values:
                    placeholders = ", ".join("?" for _ in non_blank_values)
                    value_clauses.append(f"COALESCE({expression}, '') IN ({placeholders})")
                    params.extend(non_blank_values)
                if include_blank:
                    value_clauses.append(f"COALESCE({expression}, '') = ''")
                clauses.extend(value_clauses)
        elif column.kind == "translation":
            return self._grid_child_values_clause(
                "variant_translations",
                "child_vt",
                "lang",
                column.name,
                "target_text",
                values,
            )
        elif column.kind == "remark":
            return self._grid_child_values_clause(
                "variant_remarks",
                "child_vr",
                "remark_key",
                column.name,
                "remark_value",
                values,
            )

        if not clauses:
            return None, []
        return f"({' OR '.join(clauses)})", params

    def _grid_child_values_clause(
        self,
        table: str,
        alias: str,
        key_column: str,
        key_value: str,
        value_column: str,
        values: tuple[str | None, ...],
    ) -> tuple[str | None, list[Any]]:
        non_blank_values = [value for value in values if value is not None]
        include_blank = any(value is None for value in values)
        clauses: list[str] = []
        params: list[Any] = []
        if non_blank_values:
            placeholders = ", ".join("?" for _ in non_blank_values)
            clauses.append(
                "EXISTS ("
                f"SELECT 1 FROM {table} {alias} "
                f"WHERE {alias}.variant_id = v.variant_id "
                f"AND {alias}.{key_column} = ? "
                f"AND COALESCE({alias}.{value_column}, '') IN ({placeholders})"
                ")"
            )
            params.extend([key_value, *non_blank_values])
        if include_blank:
            clauses.append(
                "NOT EXISTS ("
                f"SELECT 1 FROM {table} {alias}_blank "
                f"WHERE {alias}_blank.variant_id = v.variant_id "
                f"AND {alias}_blank.{key_column} = ? "
                f"AND COALESCE({alias}_blank.{value_column}, '') <> ''"
                ")"
            )
            params.append(key_value)
        if not clauses:
            return None, []
        return f"({' OR '.join(clauses)})", params

    def _grid_order_sql(self, spec: GridQuerySpec) -> str:
        if spec.scope_selector is not None:
            return "ORDER BY LOWER(e.business_key), v.updated_at DESC, v.variant_id DESC"
        return "ORDER BY v.updated_at DESC, v.variant_id DESC"

    def _select_variant_rows(
        self,
        where_clauses: list[str],
        params: list[Any],
        *,
        page: int,
        page_size: int | None,
        order_sql: str,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        where_sql = " AND ".join(where_clauses)
        query = f"""
            SELECT
                e.entry_id,
                e.project_id,
                e.business_key,
                v.variant_id,
                v.file_name,
                v.source,
                v.orphaned_at,
                v.trashed_at,
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
            {order_sql}
        """
        page_value = max(page, 1)
        query_params = list(params)
        if page_size is not None and page_size > 0:
            query = f"{query} LIMIT ? OFFSET ?"
            query_params.extend([page_size, (page_value - 1) * page_size])
        if conn is not None:
            rows = conn.execute(query, query_params).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(query, query_params).fetchall()
        return [dict(row) for row in rows]

    def _count_variant_rows(
        self,
        where_clauses: list[str],
        params: list[Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        where_sql = " AND ".join(where_clauses)
        query = f"""
            SELECT COUNT(*) AS count
            FROM variants v
            JOIN entries e ON e.entry_id = v.entry_id
            WHERE {where_sql}
        """
        if conn is not None:
            row = conn.execute(query, params).fetchone()
        else:
            with get_conn() as local_conn:
                row = local_conn.execute(query, params).fetchone()
        return int(row["count"] or 0)
