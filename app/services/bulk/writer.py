from __future__ import annotations

import sqlite3
from time import perf_counter
from typing import Any

from app.db import get_conn
from app.services.branch.models import BranchRef
from app.services.branch.registry import BranchRegistryService
from app.services.bulk.excel_reader import read_excel_chunks
from app.services.project.service import ProjectService
from app.services.shared.utils import now_iso
from app.services.variant.entries import EntryRepository
from app.services.variant.store import _VariantStore
from app.services.variant.bindings import _ScopeBindingStore


class BulkVariantWriter:
    def __init__(self) -> None:
        self._projects = ProjectService()
        self._registry = BranchRegistryService()
        self._entries = EntryRepository()
        self._variant_store = _VariantStore()
        self._binding_store = _ScopeBindingStore()

    def seed(
        self,
        *,
        project_id: int,
        branch_ref: BranchRef,
        workbook_path: str,
        chunk_size: int = 5000,
    ) -> dict[str, Any]:
        self._projects.require_project(project_id)
        schema = self._projects.get_schema(project_id)

        with get_conn() as conn:
            self._require_no_variants(project_id, conn=conn)
            if branch_ref.is_dev:
                self._registry.ensure_dev_branch(
                    branch_ref.branch_value, project_id=project_id, conn=conn,
                )
                self._registry.require_not_bootstrapped(
                    branch_ref.branch_value, project_id=project_id, conn=conn,
                )

            started = perf_counter()
            scope_type, scope_value = branch_ref.as_tuple()
            total_entries = 0
            total_variants = 0
            total_bindings = 0

            for chunk in read_excel_chunks(workbook_path, schema, chunk_size):
                e, v, b = self._write_chunk(
                    chunk,
                    project_id=project_id,
                    scope_type=scope_type,
                    scope_value=scope_value,
                    schema=schema,
                    conn=conn,
                )
                total_entries += e
                total_variants += v
                total_bindings += b

            if branch_ref.is_dev:
                self._mark_dev_bootstrapped(branch_ref, project_id=project_id, conn=conn)

            elapsed_ms = int((perf_counter() - started) * 1000)

        return {
            "entries_created": total_entries,
            "variants_created": total_variants,
            "bindings_created": total_bindings,
            "elapsed_ms": elapsed_ms,
        }

    def _require_no_variants(self, project_id: int, *, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt FROM variants
            WHERE entry_id IN (SELECT entry_id FROM entries WHERE project_id = ?)
            """,
            (project_id,),
        ).fetchone()
        if int(row["cnt"]) > 0:
            raise ValueError(f"project {project_id} already has variant data; cannot seed")

    def _write_chunk(
        self,
        chunk: list[dict[str, Any]],
        *,
        project_id: int,
        scope_type: str,
        scope_value: str,
        schema: dict[str, Any],
        conn: sqlite3.Connection,
    ) -> tuple[int, int, int]:
        ts = now_iso()
        business_keys = [row["business_key"] for row in chunk]

        self._entries.insert_many_ignore(project_id, business_keys, ts, conn=conn)
        entry_map = self._entries.get_by_keys(project_id, business_keys, conn=conn)

        variant_insert_rows: list[tuple[int, str, str, str]] = []
        for row in chunk:
            entry_id = int(entry_map[row["business_key"]]["entry_id"])
            variant_insert_rows.append((entry_id, row["file_name"], row["source"], ts))

        variant_ids = self._variant_store.bulk_create_variants(variant_insert_rows, conn=conn)

        translation_rows: list[tuple[int, str, str, str]] = []
        remark_rows: list[tuple[int, str, str, str]] = []
        for variant_id, row in zip(variant_ids, chunk):
            for lang, text in row["translations"].items():
                translation_rows.append((variant_id, lang, text, ts))
            for remark_key, remark_value in row["remarks"].items():
                remark_rows.append((variant_id, remark_key, remark_value, ts))

        self._variant_store.bulk_write_translations(translation_rows, conn=conn)
        self._variant_store.bulk_write_remarks(remark_rows, conn=conn)

        binding_rows: list[tuple[str, str, int, int, str]] = []
        for variant_id, row in zip(variant_ids, chunk):
            entry_id = int(entry_map[row["business_key"]]["entry_id"])
            binding_rows.append((scope_type, scope_value, entry_id, variant_id, ts))

        self._binding_store.bulk_bind(binding_rows, conn=conn)

        return len(business_keys), len(variant_ids), len(binding_rows)

    def _mark_dev_bootstrapped(
        self,
        branch_ref: BranchRef,
        *,
        project_id: int,
        conn: sqlite3.Connection,
    ) -> None:
        marker = now_iso()
        conn.execute(
            """
            UPDATE dev_versions
            SET bootstrapped_at = ?
            WHERE project_id = ? AND version = ? AND bootstrapped_at IS NULL
            """,
            (marker, project_id, branch_ref.branch_value),
        )
