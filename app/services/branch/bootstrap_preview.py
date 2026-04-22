from __future__ import annotations

from collections import Counter
from time import perf_counter
import sqlite3
from typing import Any

from app.db import get_conn, json_loads
from app.services.branch.models import BranchRef
from app.services.branch.preview_contract import EffectPreviewSummaryBuilder, effect_forecast_row
from app.services.branch.registry import BranchRegistryService
from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.variant.bindings import BindingLookupService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService


class BranchBootstrapPreviewService:
    READ_CHUNK_SIZE = 1000

    def __init__(
        self,
        *,
        imports: ImportService | None = None,
        projects: ProjectService | None = None,
        registry: BranchRegistryService | None = None,
        entries: EntryService | None = None,
        catalog: VariantCatalogService | None = None,
        binding_lookup: BindingLookupService | None = None,
    ) -> None:
        self.imports = imports or ImportService()
        self.projects = projects or ProjectService()
        self.registry = registry or BranchRegistryService()
        self.entries = entries or EntryService()
        self.catalog = catalog or VariantCatalogService()
        self.binding_lookup = binding_lookup or BindingLookupService()

    def preview(
        self,
        branch_ref: BranchRef,
        import_batch_id: int,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        if not branch_ref.is_dev:
            raise ValueError(f"bootstrap only supports dev branches: {branch_ref}")
        self.projects.require_project(project_id)
        self.imports.require_batch_project(import_batch_id, project_id)
        self._require_previewable_branch(branch_ref, project_id=project_id)

        started = perf_counter()
        with get_conn() as conn:
            rows, summary = self._preview_rows(
                branch_ref,
                import_batch_id,
                project_id=project_id,
                conn=conn,
            )
        summary["stages"] = [
            {
                "stage": "preview_branch_bootstrap",
                "elapsed_ms": int((perf_counter() - started) * 1000),
                "meta": {
                    "branch_ref": str(branch_ref),
                    "input_kind": "bootstrap",
                    "processed_count": summary["processed_count"],
                },
            }
        ]
        return {
            "preview_kind": "effect_forecast",
            "workflow_kind": "branch_bootstrap",
            "request_echo": {
                "branch_ref": str(branch_ref),
                "import_batch_id": import_batch_id,
            },
            "summary": summary,
            "rows": rows,
        }

    def _preview_rows(
        self,
        branch_ref: BranchRef,
        import_batch_id: int,
        *,
        project_id: int,
        conn: sqlite3.Connection,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        entries_by_key: dict[str, dict[str, Any]] = {}
        variants_by_entry: dict[int, list[dict[str, Any]]] = {}
        binding_rows_by_entry: dict[int, list[dict[str, Any]]] = {}
        created_entry_keys: set[str] = set()
        seen_business_keys: set[str] = set()
        status_counts: Counter[str] = Counter()
        summary_builder = EffectPreviewSummaryBuilder()
        preview_rows: list[dict[str, Any]] = []

        processed_count = 0
        last_import_row_id = 0

        while True:
            chunk_rows = self._load_chunk(import_batch_id, last_import_row_id, conn=conn)
            if not chunk_rows:
                break
            last_import_row_id = chunk_rows[-1]["import_row_id"]
            self._prime_chunk_cache(
                chunk_rows,
                project_id=project_id,
                conn=conn,
                entries_by_key=entries_by_key,
                variants_by_entry=variants_by_entry,
                binding_rows_by_entry=binding_rows_by_entry,
            )
            for row in chunk_rows:
                preview_row = self._preview_row_cached(
                    row,
                    branch_ref,
                    seen_business_keys=seen_business_keys,
                    entries_by_key=entries_by_key,
                    variants_by_entry=variants_by_entry,
                    binding_rows_by_entry=binding_rows_by_entry,
                    created_entry_keys=created_entry_keys,
                )
                processed_count += 1
                status_counts.update([str(preview_row["status"])])
                summary_builder.add_row(preview_row)
                preview_rows.append(preview_row)

        return preview_rows, {
            "branch_ref": str(branch_ref),
            "input_kind": "bootstrap",
            "import_batch_id": import_batch_id,
            "processed_count": processed_count,
            "bound_existing_variant_count": status_counts["BOUND_EXISTING_VARIANT"],
            "created_and_bound_variant_count": status_counts["CREATED_AND_BOUND_VARIANT"],
            "invalid_row_count": status_counts["INVALID_ROW"],
            "duplicate_key_count": status_counts["DUPLICATE_KEY_IN_BOOTSTRAP"],
            "created_entry_count": len(created_entry_keys),
            "created_variant_count": status_counts["CREATED_AND_BOUND_VARIANT"],
            **summary_builder.as_dict(),
        }

    def _load_chunk(
        self,
        import_batch_id: int,
        after_import_row_id: int,
        *,
        conn: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT
                import_row_id,
                file_path,
                sheet_name,
                row_index,
                business_key,
                source,
                status,
                payload_json
            FROM import_rows
            WHERE import_batch_id = ?
              AND import_row_id > ?
            ORDER BY import_row_id
            LIMIT ?
            """,
            (import_batch_id, after_import_row_id, self.READ_CHUNK_SIZE),
        ).fetchall()
        chunk_rows: list[dict[str, Any]] = []
        for row in rows:
            payload = json_loads(row["payload_json"])
            chunk_rows.append(
                {
                    "import_row_id": int(row["import_row_id"]),
                    "file_path": row["file_path"],
                    "sheet_name": row["sheet_name"],
                    "row_index": int(row["row_index"]),
                    "import_status": str(row["status"]),
                    "business_key": self._normalize_text(payload.get("business_key", row["business_key"])),
                    "source": self._normalize_text(payload.get("source", row["source"])),
                    "payload": payload,
                }
            )
        return chunk_rows

    def _prime_chunk_cache(
        self,
        chunk_rows: list[dict[str, Any]],
        *,
        project_id: int,
        conn: sqlite3.Connection,
        entries_by_key: dict[str, dict[str, Any]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
    ) -> None:
        candidate_keys = sorted(
            {
                row["business_key"]
                for row in chunk_rows
                if row["import_status"] == "ok" and row["business_key"] and row["source"]
            }
        )
        missing_lookup_keys = [key for key in candidate_keys if key not in entries_by_key]
        if missing_lookup_keys:
            entries_by_key.update(
                self.entries.get_entries_by_keys(
                    missing_lookup_keys,
                    project_id=project_id,
                    conn=conn,
                )
            )

        entry_ids_to_load = sorted(
            {
                int(entries_by_key[key]["entry_id"])
                for key in candidate_keys
                if key in entries_by_key
                and (
                    int(entries_by_key[key]["entry_id"]) not in variants_by_entry
                    or int(entries_by_key[key]["entry_id"]) not in binding_rows_by_entry
                )
            }
        )
        if not entry_ids_to_load:
            return

        variants = self.catalog.list_variants_for_entries(
            entry_ids_to_load,
            include_trashed=False,
            conn=conn,
        )
        bindings = self.binding_lookup.list_bindings_for_entries(entry_ids_to_load, conn=conn)
        for entry_id in entry_ids_to_load:
            variants_by_entry[entry_id] = list(variants.get(entry_id, []))
            binding_rows_by_entry[entry_id] = list(bindings.get(entry_id, []))

    def _preview_row_cached(
        self,
        row: dict[str, Any],
        branch_ref: BranchRef,
        *,
        seen_business_keys: set[str],
        entries_by_key: dict[str, dict[str, Any]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
        created_entry_keys: set[str],
    ) -> dict[str, Any]:
        base_row = {
            "business_key": row["business_key"],
            "file_path": row["file_path"],
            "sheet_name": row["sheet_name"],
            "row_index": row["row_index"],
        }
        if row["import_status"] != "ok" or not row["business_key"] or not row["source"]:
            return effect_forecast_row(
                {**base_row, "status": "INVALID_ROW"},
                binding_effect="none",
                variant_resolution="stay_current",
                row_outcome="invalid",
            )
        if row["business_key"] in seen_business_keys:
            return effect_forecast_row(
                {**base_row, "status": "DUPLICATE_KEY_IN_BOOTSTRAP"},
                binding_effect="none",
                variant_resolution="stay_current",
                row_outcome="invalid",
            )
        seen_business_keys.add(row["business_key"])

        entry = entries_by_key.get(row["business_key"])
        if entry is None:
            created_entry_keys.add(row["business_key"])
            return effect_forecast_row(
                {**base_row, "status": "CREATED_AND_BOUND_VARIANT"},
                binding_effect="bind",
                variant_resolution="create_new",
                row_outcome="applied",
            )

        entry_id = int(entry["entry_id"])
        bindings = binding_rows_by_entry.get(entry_id, [])
        variants = variants_by_entry.get(entry_id, [])
        current_binding = self._find_binding(bindings, branch_ref)
        source_variant = self._find_source_variant(entry_id, variants, row["source"])
        if source_variant is not None:
            return effect_forecast_row(
                {**base_row, "status": "BOUND_EXISTING_VARIANT"},
                binding_effect="bind" if current_binding is None else "rebind",
                variant_resolution="reuse_existing",
                row_outcome="applied",
            )

        return effect_forecast_row(
            {**base_row, "status": "CREATED_AND_BOUND_VARIANT"},
            binding_effect="bind" if current_binding is None else "rebind",
            variant_resolution="create_new",
            row_outcome="applied",
        )

    def _find_source_variant(
        self,
        entry_id: int,
        variants: list[dict[str, Any]],
        source: str,
    ) -> dict[str, Any] | None:
        matches = [variant for variant in variants if variant["source"] == source]
        if not matches:
            return None
        if len(matches) > 1:
            raise RuntimeError(f"duplicate active variants found for entry_id={entry_id}, source={source!r}")
        return matches[0]

    def _find_binding(self, bindings: list[dict[str, Any]], branch_ref: BranchRef) -> dict[str, Any] | None:
        scope_type, scope_value = branch_ref.as_tuple()
        for binding in bindings:
            if binding["scope_type"] == scope_type and binding["scope_value"] == scope_value:
                return binding
        return None

    def _normalize_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _require_previewable_branch(
        self,
        branch_ref: BranchRef,
        *,
        project_id: int,
    ) -> None:
        self.registry.require_not_bootstrapped(branch_ref.branch_value, project_id=project_id)


BootstrapPreviewService = BranchBootstrapPreviewService
