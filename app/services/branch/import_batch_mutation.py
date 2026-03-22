from __future__ import annotations

from collections import Counter
import sqlite3
from time import perf_counter
from typing import Any

from app.db import json_loads
from app.services.branch.models import BranchRef
from app.services.branch.policy import BranchMutationPolicy
from app.services.imports.service import ImportService
from app.services.variant.bindings import BindingLookupService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.state_coordinator import VariantStateCoordinator

from app.services.branch.variant_resolution import VariantResolutionService


class ImportBatchMutationApplier:
    def __init__(
        self,
        *,
        imports: ImportService | None = None,
        entries: EntryService | None = None,
        catalog: VariantCatalogService | None = None,
        bindings: VariantStateCoordinator | None = None,
        binding_lookup: BindingLookupService | None = None,
        resolution: VariantResolutionService | None = None,
    ) -> None:
        self.imports = imports or ImportService()
        self.entries = entries or EntryService()
        self.catalog = catalog or VariantCatalogService()
        self.bindings = bindings or VariantStateCoordinator()
        self.binding_lookup = binding_lookup or BindingLookupService()
        self.resolution = resolution or VariantResolutionService(catalog=self.catalog)

    def apply(
        self,
        branch_ref: BranchRef,
        import_batch_id: int,
        mark_as_candidate_release: bool,
        project_id: int,
        conn: sqlite3.Connection,
        version_series: str | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        self.imports.require_batch_project(import_batch_id, project_id)
        rows = conn.execute(
            """
            SELECT import_row_id, file_path, sheet_name, row_index, payload_json
            FROM import_rows
            WHERE import_batch_id = ? AND status = 'ok'
            ORDER BY import_row_id
            """,
            (import_batch_id,),
        ).fetchall()
        payload_rows = [
            {
                "import_row_id": int(row["import_row_id"]),
                "file_path": row["file_path"],
                "sheet_name": row["sheet_name"],
                "row_index": int(row["row_index"]),
                "payload": json_loads(row["payload_json"]),
            }
            for row in rows
        ]
        business_keys = [row["payload"]["business_key"] for row in payload_rows]
        existing_entries_by_key = self.entries.get_entries_by_keys(business_keys, project_id=project_id, conn=conn)
        missing_entry_keys = {key for key in business_keys if key not in existing_entries_by_key}
        entries_by_key = self.entries.ensure_entries(business_keys, project_id=project_id, conn=conn)
        entry_ids = [int(entry["entry_id"]) for entry in entries_by_key.values()]
        variants_by_entry = self.catalog.list_variants_for_entries(entry_ids, include_trashed=False, conn=conn)
        binding_rows_by_entry = {
            entry_id: self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn)
            for entry_id in entry_ids
        }

        status_counts: Counter[str] = Counter()
        report_rows: list[dict[str, Any]] = []
        for row in payload_rows:
            payload = row["payload"]
            entry = entries_by_key[payload["business_key"]]
            entry_id = int(entry["entry_id"])
            variants_by_entry.setdefault(entry_id, [])
            status = self._apply_row_cached(
                entry_id,
                payload,
                branch_ref,
                binding_rows_by_entry,
                variants_by_entry,
                conn=conn,
            )
            status_counts.update([status])
            report_rows.append(
                {
                    "business_key": payload["business_key"],
                    "file_path": row["file_path"],
                    "sheet_name": row["sheet_name"],
                    "row_index": row["row_index"],
                    "status": status,
                }
            )

        summary = {
            "branch_ref": str(branch_ref),
            "input_kind": "import_batch",
            "import_batch_id": import_batch_id,
            "mark_as_candidate_release": mark_as_candidate_release,
            "version_series": version_series,
            "processed_count": len(report_rows),
            "created_entry_count": len(set(missing_entry_keys)),
            **self._status_summary(status_counts),
            "stages": [
                {
                    "stage": "apply_scope_mutation",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {
                        "branch_ref": str(branch_ref),
                        "input_kind": "import_batch",
                        "processed_count": len(report_rows),
                    },
                }
            ],
        }
        return {"summary": summary, "report_rows": report_rows}

    def _apply_row_cached(
        self,
        entry_id: int,
        payload: dict[str, Any],
        target_branch: BranchRef,
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
        conn: sqlite3.Connection,
    ) -> str:
        bindings = binding_rows_by_entry.get(entry_id, [])
        variants = variants_by_entry.get(entry_id, [])
        current_binding = self._find_binding(bindings, target_branch)
        source_variant = self.resolution.find_source_variant_in_cache(entry_id, variants, payload["source"])

        if source_variant is None:
            variant_id = self.catalog.create_variant(
                entry_id,
                self.catalog.build_content(
                    payload.get("file_name"),
                    payload["source"],
                    payload.get("translations", {}),
                    payload.get("remarks", {}),
                ),
                conn=conn,
            )
            self.bindings.bind_scope(entry_id, target_branch, variant_id, conn=conn)
            self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry, conn=conn)
            return "CREATED_AND_BOUND_VARIANT"

        variant_id = int(source_variant["variant_id"])
        current_matches = current_binding is not None and int(current_binding["variant_id"]) == variant_id
        bound_branch_refs = self.resolution.bound_branch_refs_for_variant(bindings, variant_id)
        if not BranchMutationPolicy.for_branch(target_branch).can_update_hit_variant(target_branch, bound_branch_refs):
            if current_matches:
                return "NOOP"
            self.bindings.bind_scope(entry_id, target_branch, variant_id, conn=conn)
            self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry, conn=conn)
            return "BOUND_EXISTING_VARIANT"

        payload_matches = self.resolution.payload_matches_variant(source_variant, payload)
        if payload_matches:
            if current_matches:
                return "NOOP"
            self.bindings.bind_scope(entry_id, target_branch, variant_id, conn=conn)
            self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry, conn=conn)
            return "BOUND_EXISTING_VARIANT"

        self.catalog.update_variant(
            variant_id,
            self.catalog.build_content(
                payload.get("file_name"),
                payload["source"],
                payload.get("translations", {}),
                payload.get("remarks", {}),
            ),
            conn=conn,
        )
        if current_matches:
            status = "UPDATED_BOUND_VARIANT"
        else:
            self.bindings.bind_scope(entry_id, target_branch, variant_id, conn=conn)
            status = "UPDATED_AND_BOUND_EXISTING_VARIANT"
        self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry, conn=conn)
        return status

    def _status_summary(self, status_counts: Counter[str]) -> dict[str, int]:
        return {
            "updated_bound_variant_count": status_counts["UPDATED_BOUND_VARIANT"],
            "bound_existing_variant_count": status_counts["BOUND_EXISTING_VARIANT"],
            "updated_and_bound_existing_variant_count": status_counts["UPDATED_AND_BOUND_EXISTING_VARIANT"],
            "created_and_bound_variant_count": status_counts["CREATED_AND_BOUND_VARIANT"],
            "missing_in_scope_count": status_counts["MISSING_IN_SCOPE"],
            "noop_count": status_counts["NOOP"],
        }

    def _refresh_entry_cache(
        self,
        entry_id: int,
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
        conn: sqlite3.Connection,
    ) -> None:
        binding_rows_by_entry[entry_id] = self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn)
        variants_by_entry[entry_id] = self.catalog.list_variants(entry_id, include_trashed=False, conn=conn)

    def _find_binding(self, bindings: list[dict[str, Any]], branch_ref: BranchRef) -> dict[str, Any] | None:
        scope_type, scope_value = branch_ref.as_tuple()
        for binding in bindings:
            if binding["scope_type"] == scope_type and binding["scope_value"] == scope_value:
                return binding
        return None
