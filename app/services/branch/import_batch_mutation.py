from __future__ import annotations

from collections import Counter
import sqlite3
from time import perf_counter
from typing import Any, Generator

from app.db import json_loads
from app.services.branch.models import BranchRef
from app.services.branch.mutation_semantics import (
    MutationSemanticSummaryBuilder,
    semantics_row,
)
from app.services.branch.policy import AuthorityPolicy
from app.services.imports.service import ImportService
from app.services.variant.bindings import BindingLookupService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.state_coordinator import VariantStateCoordinator

from app.services.branch.variant_resolution import VariantResolutionService


class ImportBatchMutationApplier:
    READ_CHUNK_SIZE = 1000

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
        project_id: int,
        conn: sqlite3.Connection,
        version_series: str | None = None,
    ) -> dict[str, Any]:
        report_rows: list[dict[str, Any]] = []
        row_stream = self.iter_apply(
            branch_ref,
            import_batch_id,
            project_id,
            conn,
            version_series=version_series,
        )
        iterator = iter(row_stream)
        while True:
            try:
                report_rows.append(next(iterator))
            except StopIteration as stop:
                summary = dict((stop.value or {}).get("summary", {}))
                break
        return {"summary": summary, "report_rows": report_rows}

    def iter_apply(
        self,
        branch_ref: BranchRef,
        import_batch_id: int,
        project_id: int,
        conn: sqlite3.Connection,
        version_series: str | None = None,
    ) -> Generator[dict[str, Any], None, dict[str, Any]]:
        started = perf_counter()
        self.imports.require_batch_project(import_batch_id, project_id)

        entries_by_key: dict[str, dict[str, Any]] = {}
        variants_by_entry: dict[int, list[dict[str, Any]]] = {}
        binding_rows_by_entry: dict[int, list[dict[str, Any]]] = {}
        created_entry_keys: set[str] = set()
        status_counts: Counter[str] = Counter()
        semantic_counts = MutationSemanticSummaryBuilder()
        filtered_count = 0

        processed_count = 0
        last_import_row_id = 0
        while True:
            payload_rows = self._load_chunk(import_batch_id, last_import_row_id, conn=conn)
            if not payload_rows:
                break
            last_import_row_id = payload_rows[-1]["import_row_id"]
            self._prime_chunk_cache(
                payload_rows,
                project_id=project_id,
                conn=conn,
                entries_by_key=entries_by_key,
                variants_by_entry=variants_by_entry,
                binding_rows_by_entry=binding_rows_by_entry,
                created_entry_keys=created_entry_keys,
            )
            touched_entry_ids: set[int] = set()
            for row in payload_rows:
                payload = row["payload"]
                entry = entries_by_key[payload["business_key"]]
                entry_id = int(entry["entry_id"])
                status = self._apply_row_cached(
                    entry_id,
                    payload,
                    branch_ref,
                    binding_rows_by_entry,
                    variants_by_entry,
                    touched_entry_ids=touched_entry_ids,
                    conn=conn,
                )
                status_counts.update([status["status"]])
                semantic_counts.add_row(status)
                filtered_count += int(bool(status.get("content_filtered_by_authority")))
                processed_count += 1
                report_row = {
                    "business_key": payload["business_key"],
                    "file_path": row["file_path"],
                    "sheet_name": row["sheet_name"],
                    "row_index": row["row_index"],
                    "status": status["status"],
                    "mutation_class": status["mutation_class"],
                    "binding_effect": status["binding_effect"],
                    "content_effect": status["content_effect"],
                    "variant_resolution": status["variant_resolution"],
                    "row_outcome": status["row_outcome"],
                }
                if status.get("content_filtered_by_authority"):
                    report_row["content_filtered_by_authority"] = True
                yield report_row
            if touched_entry_ids:
                self.bindings.refresh_orphan_states(list(touched_entry_ids), conn=conn)

        summary = {
            "branch_ref": str(branch_ref),
            "input_kind": "import_batch",
            "import_batch_id": import_batch_id,
            "version_series": version_series,
            "processed_count": processed_count,
            "created_entry_count": len(created_entry_keys),
            **self._status_summary(status_counts, filtered_count=filtered_count),
            **semantic_counts.as_dict(),
            "stages": [
                {
                    "stage": "apply_scope_mutation",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {
                        "branch_ref": str(branch_ref),
                        "input_kind": "import_batch",
                        "processed_count": processed_count,
                    },
                }
            ],
        }
        return {"summary": summary}

    def _apply_row_cached(
        self,
        entry_id: int,
        payload: dict[str, Any],
        target_branch: BranchRef,
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
        touched_entry_ids: set[int],
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        bindings = binding_rows_by_entry.get(entry_id, [])
        variants = variants_by_entry.get(entry_id, [])
        current_binding = self._find_binding(bindings, target_branch)
        current_variant = self._find_variant_by_id(
            variants,
            int(current_binding["variant_id"]),
        ) if current_binding is not None else None
        change = {
            "business_key": payload["business_key"],
            "source": payload["source"],
            "translations_by_lang": payload.get("translations", {}),
            "remarks_by_key": payload.get("remarks", {}),
            "file_name": payload.get("file_name"),
        }
        requested_source = payload["source"]

        if current_variant is not None and requested_source == current_variant["source"]:
            merged = self.resolution.merged_variant_payload(current_variant, change, requested_source)
            if self.resolution.variant_matches(current_variant, merged):
                return semantics_row(
                    {"status": "NOOP"},
                    mutation_class="content",
                    binding_effect="none",
                    content_effect="none",
                    variant_resolution="stay_current",
                    row_outcome="noop",
                )
            bound_branch_refs = self.resolution.bound_branch_refs_for_variant(
                bindings,
                int(current_variant["variant_id"]),
            )
            decision = AuthorityPolicy.evaluate_content_edit(
                target_branch,
                bound_branch_refs,
                content_changed=not self.resolution.variant_matches(current_variant, merged),
            )
            if decision.filtered:
                return semantics_row(
                    {
                        "status": "NOOP",
                        "content_filtered_by_authority": True,
                    },
                    mutation_class="content",
                    binding_effect="none",
                    content_effect="filtered",
                    variant_resolution="stay_current",
                    row_outcome="noop",
                )
            self.catalog.update_variant(
                int(current_variant["variant_id"]),
                merged,
                actor_scope=target_branch.as_tuple(),
                conn=conn,
            )
            self._update_variant_cache(variants, int(current_variant["variant_id"]), merged)
            return semantics_row(
                {"status": "UPDATED_BOUND_VARIANT"},
                mutation_class="content",
                binding_effect="none",
                content_effect="update",
                variant_resolution="stay_current",
                row_outcome="applied",
            )

        source_variant = self.resolution.find_source_variant_in_cache(entry_id, variants, requested_source)
        content_base = source_variant
        merged = self.resolution.merged_variant_payload(content_base, change, requested_source)

        if source_variant is None:
            variant_id = self.catalog.create_variant(
                entry_id,
                merged,
                conn=conn,
            )
            self._append_variant_cache(variants, entry_id, variant_id, merged)
            self.bindings.bind(
                entry_id,
                target_branch,
                variant_id,
                conn=conn,
                refresh_orphan_states=False,
            )
            self._upsert_binding_cache(bindings, target_branch, entry_id, variant_id)
            touched_entry_ids.add(entry_id)
            return semantics_row(
                {"status": "CREATED_AND_BOUND_VARIANT"},
                mutation_class="range",
                binding_effect="bind" if current_binding is None else "rebind",
                content_effect="create",
                variant_resolution="create_new",
                row_outcome="applied",
            )

        variant_id = int(source_variant["variant_id"])
        current_matches = current_binding is not None and int(current_binding["variant_id"]) == variant_id
        bound_branch_refs = self.resolution.bound_branch_refs_for_variant(bindings, variant_id)
        payload_matches_target = self.resolution.variant_matches(source_variant, merged)
        decision = AuthorityPolicy.evaluate_content_edit(
            target_branch,
            bound_branch_refs,
            content_changed=not payload_matches_target,
        )
        if decision.filtered:
            row = {
                "status": "NOOP" if current_matches else "BOUND_EXISTING_VARIANT",
                "content_filtered_by_authority": True,
            }
            if current_matches:
                return semantics_row(
                    row,
                    mutation_class="range",
                    binding_effect="none",
                    content_effect="filtered",
                    variant_resolution="stay_current",
                    row_outcome="noop",
                )
            self.bindings.bind(
                entry_id,
                target_branch,
                variant_id,
                conn=conn,
                refresh_orphan_states=False,
            )
            self._upsert_binding_cache(bindings, target_branch, entry_id, variant_id)
            touched_entry_ids.add(entry_id)
            return semantics_row(
                row,
                mutation_class="range",
                binding_effect="bind" if current_binding is None else "rebind",
                content_effect="filtered",
                variant_resolution="reuse_existing",
                row_outcome="applied",
            )
        if current_matches and payload_matches_target:
            return semantics_row(
                {"status": "NOOP"},
                mutation_class="range",
                binding_effect="none",
                content_effect="none",
                variant_resolution="stay_current",
                row_outcome="noop",
            )
        if payload_matches_target:
            self.bindings.bind(
                entry_id,
                target_branch,
                variant_id,
                conn=conn,
                refresh_orphan_states=False,
            )
            self._upsert_binding_cache(bindings, target_branch, entry_id, variant_id)
            touched_entry_ids.add(entry_id)
            return semantics_row(
                {"status": "BOUND_EXISTING_VARIANT"},
                mutation_class="range",
                binding_effect="bind" if current_binding is None else "rebind",
                content_effect="none",
                variant_resolution="reuse_existing",
                row_outcome="applied",
            )

        self.catalog.update_variant(
            variant_id,
            merged,
            actor_scope=target_branch.as_tuple(),
            conn=conn,
        )
        self._update_variant_cache(variants, variant_id, merged)
        if current_matches:
            return semantics_row(
                {"status": "UPDATED_BOUND_VARIANT"},
                mutation_class="content",
                binding_effect="none",
                content_effect="update",
                variant_resolution="stay_current",
                row_outcome="applied",
            )
        self.bindings.bind(
            entry_id,
            target_branch,
            variant_id,
            conn=conn,
            refresh_orphan_states=False,
        )
        self._upsert_binding_cache(bindings, target_branch, entry_id, variant_id)
        touched_entry_ids.add(entry_id)
        return semantics_row(
            {"status": "UPDATED_AND_BOUND_EXISTING_VARIANT"},
            mutation_class="range",
            binding_effect="bind" if current_binding is None else "rebind",
            content_effect="update",
            variant_resolution="reuse_existing",
            row_outcome="applied",
        )

    def _status_summary(self, status_counts: Counter[str], *, filtered_count: int) -> dict[str, int]:
        return {
            "updated_bound_variant_count": status_counts["UPDATED_BOUND_VARIANT"],
            "bound_existing_variant_count": status_counts["BOUND_EXISTING_VARIANT"],
            "updated_and_bound_existing_variant_count": status_counts["UPDATED_AND_BOUND_EXISTING_VARIANT"],
            "created_and_bound_variant_count": status_counts["CREATED_AND_BOUND_VARIANT"],
            "missing_in_scope_count": status_counts["MISSING_IN_SCOPE"],
            "noop_count": status_counts["NOOP"],
            "forbidden_by_authority_count": status_counts["FORBIDDEN_BY_AUTHORITY"],
            "content_filtered_by_authority_count": filtered_count,
        }

    def _load_chunk(
        self,
        import_batch_id: int,
        after_import_row_id: int,
        conn: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT import_row_id, file_path, sheet_name, row_index, payload_json
            FROM import_rows
            WHERE import_batch_id = ?
              AND status = 'ok'
              AND import_row_id > ?
            ORDER BY import_row_id
            LIMIT ?
            """,
            (import_batch_id, after_import_row_id, self.READ_CHUNK_SIZE),
        ).fetchall()
        return [
            {
                "import_row_id": int(row["import_row_id"]),
                "file_path": row["file_path"],
                "sheet_name": row["sheet_name"],
                "row_index": int(row["row_index"]),
                "payload": json_loads(row["payload_json"]),
            }
            for row in rows
        ]

    def _prime_chunk_cache(
        self,
        payload_rows: list[dict[str, Any]],
        *,
        project_id: int,
        conn: sqlite3.Connection,
        entries_by_key: dict[str, dict[str, Any]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
        created_entry_keys: set[str],
    ) -> None:
        business_keys = sorted({row["payload"]["business_key"] for row in payload_rows})
        missing_lookup_keys = [key for key in business_keys if key not in entries_by_key]
        if missing_lookup_keys:
            existing = self.entries.get_entries_by_keys(
                missing_lookup_keys,
                project_id=project_id,
                conn=conn,
            )
            entries_by_key.update(existing)
            missing_create_keys = [key for key in missing_lookup_keys if key not in existing]
            if missing_create_keys:
                created_entry_keys.update(missing_create_keys)
                entries_by_key.update(
                    self.entries.ensure_entries(
                        missing_create_keys,
                        project_id=project_id,
                        conn=conn,
                    )
                )

        entry_ids_to_load = sorted(
            {
                int(entries_by_key[key]["entry_id"])
                for key in business_keys
                if int(entries_by_key[key]["entry_id"]) not in variants_by_entry
                or int(entries_by_key[key]["entry_id"]) not in binding_rows_by_entry
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

    def _find_variant_by_id(
        self,
        variants: list[dict[str, Any]],
        variant_id: int,
    ) -> dict[str, Any] | None:
        for variant in variants:
            if int(variant["variant_id"]) == variant_id:
                return variant
        return None

    def _append_variant_cache(
        self,
        variants: list[dict[str, Any]],
        entry_id: int,
        variant_id: int,
        content: dict[str, Any],
    ) -> None:
        variants.append(
            {
                "variant_id": variant_id,
                "entry_id": entry_id,
                "file_name": content["file_name"],
                "source": content["source"],
                "translations": dict(content["translations"]),
                "remarks": dict(content["remarks"]),
                "orphaned_at": None,
                "trashed_at": None,
                "created_at": "",
                "updated_at": "",
            }
        )

    def _update_variant_cache(
        self,
        variants: list[dict[str, Any]],
        variant_id: int,
        content: dict[str, Any],
    ) -> None:
        variant = self._find_variant_by_id(variants, variant_id)
        if variant is None:
            return
        variant["file_name"] = content["file_name"]
        variant["source"] = content["source"]
        variant["translations"] = dict(content["translations"])
        variant["remarks"] = dict(content["remarks"])

    def _upsert_binding_cache(
        self,
        bindings: list[dict[str, Any]],
        branch_ref: BranchRef,
        entry_id: int,
        variant_id: int,
    ) -> None:
        scope_type, scope_value = branch_ref.as_tuple()
        for binding in bindings:
            if binding["scope_type"] == scope_type and binding["scope_value"] == scope_value:
                binding["variant_id"] = variant_id
                return
        bindings.append(
            {
                "scope_type": scope_type,
                "scope_value": scope_value,
                "entry_id": entry_id,
                "variant_id": variant_id,
                "created_at": "",
                "updated_at": "",
            }
        )

    def _find_binding(self, bindings: list[dict[str, Any]], branch_ref: BranchRef) -> dict[str, Any] | None:
        scope_type, scope_value = branch_ref.as_tuple()
        for binding in bindings:
            if binding["scope_type"] == scope_type and binding["scope_value"] == scope_value:
                return binding
        return None
