from __future__ import annotations

from collections.abc import Callable, Iterable
from collections import Counter
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import sqlite3

from app.services.branch.models import BranchRef
from app.services.branch.mutation_semantics import MutationSemanticSummaryBuilder, semantics_row
from app.services.branch.policy import AuthorityPolicy
from app.services.branch.variant_resolution import VariantResolutionService
from app.services.project.service import ProjectService
from app.services.shared.io import (
    normalize_content_map,
    normalize_non_content_map,
    normalize_non_content_value,
)
from app.services.shared.utils import now_iso
from app.services.variant.bindings import BindingLookupService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.workbooks.batches import WorkbookBatchService


@dataclass
class _ResolvedContentRow:
    row: dict[str, Any]
    entry: dict[str, Any] | None = None
    binding: dict[str, Any] | None = None
    variant: dict[str, Any] | None = None
    bound_refs: list[BranchRef] = field(default_factory=list)


@dataclass
class _ContentWriteSet:
    translation_rows: list[tuple[int, str, str, str]] = field(default_factory=list)
    remark_rows: list[tuple[int, str, str, str]] = field(default_factory=list)
    variant_file_rows: list[tuple[int, str, str]] = field(default_factory=list)
    pivot_changed_rows: list[tuple[int, str, str, str]] = field(default_factory=list)


class ContentBatchMutationApplier:
    READ_CHUNK_SIZE = 1000

    def __init__(
        self,
        *,
        batches: WorkbookBatchService | None = None,
        entries: EntryService | None = None,
        catalog: VariantCatalogService | None = None,
        binding_lookup: BindingLookupService | None = None,
        projects: ProjectService | None = None,
        resolution: VariantResolutionService | None = None,
    ) -> None:
        self.batches = batches or WorkbookBatchService()
        self.entries = entries or EntryService()
        self.catalog = catalog or VariantCatalogService()
        self.binding_lookup = binding_lookup or BindingLookupService()
        self.projects = projects or ProjectService()
        self.resolution = resolution or VariantResolutionService(catalog=self.catalog)

    def apply(
        self,
        branch_ref: BranchRef,
        workbook_batch_id: int,
        project_id: int,
        conn: sqlite3.Connection,
        *,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        progress_interval: int = 0,
        max_elapsed_seconds: float | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        status_counts: Counter[str] = Counter()
        semantic_counts = MutationSemanticSummaryBuilder()
        report_rows: list[dict[str, Any]] = []
        filtered_count = 0
        schema = self.projects.get_schema(project_id)

        for chunk in self.batches.iter_row_chunks(
            workbook_batch_id,
            project_id,
            ok_only=True,
            chunk_size=self.READ_CHUNK_SIZE,
        ):
            elapsed_seconds = perf_counter() - started
            if max_elapsed_seconds is not None and elapsed_seconds > max_elapsed_seconds:
                raise TimeoutError(
                    "content mutation exceeded "
                    f"{max_elapsed_seconds:.1f}s after {len(report_rows)} rows"
                )
            for report_row in self._apply_chunk(branch_ref, chunk, project_id, schema, conn):
                status_counts.update([report_row["status"]])
                semantic_counts.add_row(report_row)
                filtered_count += int(bool(report_row.get("content_filtered_by_authority")))
                report_rows.append(report_row)
                if (
                    progress_callback is not None
                    and progress_interval > 0
                    and len(report_rows) % progress_interval == 0
                ):
                    progress_callback(
                        self._progress_payload(
                            branch_ref,
                            workbook_batch_id,
                            len(report_rows),
                            status_counts,
                            filtered_count=filtered_count,
                            started=started,
                        )
                    )

        summary = {
            "branch_ref": str(branch_ref),
            "input_kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": workbook_batch_id,
            "processed_count": len(report_rows),
            "updated_bound_variant_count": status_counts["UPDATED_BOUND_VARIANT"],
            "source_mismatch_count": status_counts["SOURCE_MISMATCH"],
            "missing_in_scope_count": status_counts["MISSING_IN_SCOPE"],
            "noop_count": status_counts["NOOP"],
            "content_filtered_by_authority_count": filtered_count,
            **semantic_counts.as_dict(),
            "stages": [
                {
                    "stage": "apply_content_mutation",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {"processed_count": len(report_rows)},
                }
            ],
        }
        return {"summary": summary, "report_rows": report_rows}

    def _progress_payload(
        self,
        branch_ref: BranchRef,
        workbook_batch_id: int,
        processed_count: int,
        status_counts: Counter[str],
        *,
        filtered_count: int,
        started: float,
    ) -> dict[str, Any]:
        return {
            "branch_ref": str(branch_ref),
            "input_kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": workbook_batch_id,
            "processed_count": processed_count,
            "updated_bound_variant_count": status_counts["UPDATED_BOUND_VARIANT"],
            "source_mismatch_count": status_counts["SOURCE_MISMATCH"],
            "missing_in_scope_count": status_counts["MISSING_IN_SCOPE"],
            "noop_count": status_counts["NOOP"],
            "content_filtered_by_authority_count": filtered_count,
            "elapsed_ms": int((perf_counter() - started) * 1000),
        }

    def _apply_chunk(
        self,
        branch_ref: BranchRef,
        rows: list[dict[str, Any]],
        project_id: int,
        schema: dict[str, Any],
        conn: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        timestamp = now_iso()
        write_set = _ContentWriteSet()
        report_rows: list[dict[str, Any]] = []

        for resolved in self._resolve_chunk(branch_ref, rows, project_id, conn):
            row = resolved.row
            payload = row["payload"]
            if resolved.entry is None or resolved.binding is None or resolved.variant is None:
                report_rows.append(
                    self._report(row, "MISSING_IN_SCOPE", "none", "none", "stay_current", "missing")
                )
                continue

            variant = resolved.variant
            requested_source = normalize_non_content_value(payload["source"])
            if variant["source"] != requested_source:
                report_rows.append(
                    self._report(row, "SOURCE_MISMATCH", "none", "none", "stay_current", "missing")
                )
                continue

            merged = self._merge_schema_payload(variant, payload)
            variant_id = int(variant["variant_id"])
            if self.resolution.variant_matches(variant, merged):
                report_rows.append(
                    self._report(
                        row,
                        "NOOP",
                        "none",
                        "none",
                        "stay_current",
                        "noop",
                        variant_id=variant_id,
                    )
                )
                continue

            decision = AuthorityPolicy.evaluate_content_edit(
                branch_ref,
                resolved.bound_refs,
                content_changed=True,
            )
            if decision.filtered:
                report_rows.append(
                    self._report(
                        row,
                        "NOOP",
                        "none",
                        "filtered",
                        "stay_current",
                        "noop",
                        variant_id=variant_id,
                        content_filtered_by_authority=True,
                    )
                )
                continue

            self._append_sparse_writes(write_set, variant, merged, timestamp)
            if self._pivot_language_changed(schema, variant, merged):
                scope_type, scope_value = branch_ref.as_tuple()
                write_set.pivot_changed_rows.append((variant_id, scope_type, scope_value, timestamp))
            self._update_variant_cache_after_write(variant, merged)
            report_rows.append(
                self._report(
                    row,
                    "UPDATED_BOUND_VARIANT",
                    "none",
                    "update",
                    "stay_current",
                    "applied",
                    variant_id=variant_id,
                )
            )

        self._flush_write_set(write_set, conn)
        return report_rows

    def _resolve_chunk(
        self,
        branch_ref: BranchRef,
        rows: list[dict[str, Any]],
        project_id: int,
        conn: sqlite3.Connection,
    ) -> list[_ResolvedContentRow]:
        business_keys = self._unique_preserving_order(
            normalize_non_content_value(row["payload"]["business_key"])
            for row in rows
        )
        entries_by_key = self.entries.get_entries_by_keys(business_keys, project_id=project_id, conn=conn)
        entry_ids = self._unique_preserving_order(
            int(entry["entry_id"])
            for entry in entries_by_key.values()
        )
        target_bindings = self.binding_lookup.get_bindings_for_entries(entry_ids, branch_ref, conn=conn)
        variant_ids = self._unique_preserving_order(
            int(binding["variant_id"])
            for binding in target_bindings.values()
        )
        variants = self.catalog.get_variants(variant_ids, conn=conn)
        missing_variant_ids = [variant_id for variant_id in variant_ids if variant_id not in variants]
        if len(missing_variant_ids) == 1:
            raise KeyError(f"variant not found: {missing_variant_ids[0]}")
        if missing_variant_ids:
            raise KeyError(f"variants not found: {missing_variant_ids}")
        bindings_by_entry = self.binding_lookup.list_bindings_for_entries(entry_ids, conn=conn)

        resolved_rows: list[_ResolvedContentRow] = []
        for row in rows:
            business_key = normalize_non_content_value(row["payload"]["business_key"])
            entry = entries_by_key.get(business_key)
            binding = target_bindings.get(int(entry["entry_id"])) if entry is not None else None
            variant = variants.get(int(binding["variant_id"])) if binding is not None else None
            bound_refs: list[BranchRef] = []
            if entry is not None and variant is not None:
                bound_refs = self.resolution.bound_branch_refs_for_variant(
                    bindings_by_entry.get(int(entry["entry_id"]), []),
                    int(variant["variant_id"]),
                )
            resolved_rows.append(
                _ResolvedContentRow(
                    row=row,
                    entry=entry,
                    binding=binding,
                    variant=variant,
                    bound_refs=bound_refs,
                )
            )
        return resolved_rows

    def _merge_schema_payload(self, variant: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        translations = dict(variant.get("translations") or {})
        translations.update(payload.get("translations") or {})
        remarks = dict(variant.get("remarks") or {})
        remarks.update(payload.get("remarks") or {})
        file_name = payload.get("file_name")
        if file_name is None:
            file_name = variant.get("file_name")
        return {
            "file_name": normalize_non_content_value(file_name),
            "source": normalize_non_content_value(payload["source"]),
            "translations": normalize_content_map(translations),
            "remarks": normalize_non_content_map(remarks),
        }

    def _append_sparse_writes(
        self,
        write_set: _ContentWriteSet,
        variant: dict[str, Any],
        merged: dict[str, Any],
        timestamp: str,
    ) -> None:
        variant_id = int(variant["variant_id"])
        current_translations = dict(variant.get("translations") or {})
        for lang, value in dict(merged["translations"]).items():
            if current_translations.get(lang) != value:
                write_set.translation_rows.append((variant_id, lang, value, timestamp))
        current_remarks = dict(variant.get("remarks") or {})
        for remark_key, value in dict(merged["remarks"]).items():
            if current_remarks.get(remark_key) != value:
                write_set.remark_rows.append((variant_id, remark_key, value, timestamp))
        write_set.variant_file_rows.append((variant_id, str(merged["file_name"]), timestamp))

    def _pivot_language_changed(
        self,
        schema: dict[str, Any],
        variant: dict[str, Any],
        merged: dict[str, Any],
    ) -> bool:
        pivot_language = schema.get("pivot_language")
        if pivot_language is None:
            return False
        old_value = normalize_content_map(
            {pivot_language: dict(variant.get("translations") or {}).get(pivot_language)}
        )[pivot_language]
        new_value = normalize_content_map(
            {pivot_language: dict(merged["translations"]).get(pivot_language)}
        )[pivot_language]
        return old_value != new_value

    def _flush_write_set(self, write_set: _ContentWriteSet, conn: sqlite3.Connection) -> None:
        self.catalog.bulk_upsert_translations(write_set.translation_rows, conn=conn)
        self.catalog.bulk_upsert_remarks(write_set.remark_rows, conn=conn)
        self.catalog.bulk_update_variant_files(
            list(self._dedupe_by_variant_id(write_set.variant_file_rows).values()),
            conn=conn,
        )
        self.catalog.bulk_set_pivot_changed(
            list(self._dedupe_by_variant_id(write_set.pivot_changed_rows).values()),
            conn=conn,
        )

    def _update_variant_cache_after_write(self, variant: dict[str, Any], merged: dict[str, Any]) -> None:
        variant["file_name"] = merged["file_name"]
        variant["source"] = merged["source"]
        variant["translations"] = dict(merged["translations"])
        variant["remarks"] = dict(merged["remarks"])

    def _unique_preserving_order(self, values: Iterable[Any]) -> list[Any]:
        seen: set[Any] = set()
        unique: list[Any] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            unique.append(value)
        return unique

    def _dedupe_by_variant_id(self, rows: list[tuple[Any, ...]]) -> dict[int, tuple[Any, ...]]:
        return {int(row[0]): row for row in rows}

    def _report(
        self,
        row: dict[str, Any],
        status: str,
        binding_effect: str,
        content_effect: str,
        variant_resolution: str,
        row_outcome: str,
        *,
        variant_id: int | None = None,
        content_filtered_by_authority: bool = False,
    ) -> dict[str, Any]:
        report = {
            "business_key": row["business_key"],
            "file_path": row["file_path"],
            "sheet_name": row["sheet_name"],
            "row_index": row["row_index"],
            "status": status,
        }
        if variant_id is not None:
            report["variant_id"] = variant_id
        if content_filtered_by_authority:
            report["content_filtered_by_authority"] = True
        return semantics_row(
            report,
            mutation_class="content",
            binding_effect=binding_effect,
            content_effect=content_effect,
            variant_resolution=variant_resolution,
            row_outcome=row_outcome,
        )
