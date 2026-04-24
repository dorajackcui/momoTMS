from __future__ import annotations

from collections import Counter
from time import perf_counter
from typing import Any

import sqlite3

from app.services.branch.models import BranchRef
from app.services.branch.mutation_semantics import MutationSemanticSummaryBuilder, semantics_row
from app.services.branch.policy import AuthorityPolicy
from app.services.branch.variant_resolution import VariantResolutionService
from app.services.variant.bindings import BindingLookupService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.workbooks.batches import WorkbookBatchService


class ContentBatchMutationApplier:
    def __init__(
        self,
        *,
        batches: WorkbookBatchService | None = None,
        entries: EntryService | None = None,
        catalog: VariantCatalogService | None = None,
        binding_lookup: BindingLookupService | None = None,
        resolution: VariantResolutionService | None = None,
    ) -> None:
        self.batches = batches or WorkbookBatchService()
        self.entries = entries or EntryService()
        self.catalog = catalog or VariantCatalogService()
        self.binding_lookup = binding_lookup or BindingLookupService()
        self.resolution = resolution or VariantResolutionService(catalog=self.catalog)

    def apply(
        self,
        branch_ref: BranchRef,
        workbook_batch_id: int,
        project_id: int,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        started = perf_counter()
        status_counts: Counter[str] = Counter()
        semantic_counts = MutationSemanticSummaryBuilder()
        report_rows: list[dict[str, Any]] = []
        filtered_count = 0

        for row in self.batches.iter_rows(workbook_batch_id, project_id, ok_only=True):
            report_row = self._apply_row(branch_ref, row, project_id, conn)
            status_counts.update([report_row["status"]])
            semantic_counts.add_row(report_row)
            filtered_count += int(bool(report_row.get("content_filtered_by_authority")))
            report_rows.append(report_row)

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

    def _apply_row(
        self,
        branch_ref: BranchRef,
        row: dict[str, Any],
        project_id: int,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        payload = row["payload"]
        business_key = payload["business_key"]
        requested_source = payload["source"]
        entry = self.entries.get_entry(business_key, project_id=project_id, conn=conn)
        if entry is None:
            return self._report(row, "MISSING_IN_SCOPE", "none", "none", "stay_current", "missing")

        entry_id = int(entry["entry_id"])
        binding = self.binding_lookup.get_binding(entry_id, branch_ref, conn=conn)
        if binding is None:
            return self._report(row, "MISSING_IN_SCOPE", "none", "none", "stay_current", "missing")

        current_variant = self.catalog.get_variant(int(binding["variant_id"]), conn=conn)
        if current_variant["source"] != requested_source:
            return self._report(row, "SOURCE_MISMATCH", "none", "none", "stay_current", "missing")

        change = {
            "business_key": business_key,
            "source": requested_source,
            "translations_by_lang": payload.get("translations", {}),
            "remarks_by_key": payload.get("remarks", {}),
            "file_name": payload.get("file_name"),
        }
        merged = self.resolution.merged_variant_payload(current_variant, change, requested_source)
        if self.resolution.variant_matches(current_variant, merged):
            return self._report(row, "NOOP", "none", "none", "stay_current", "noop", variant_id=int(current_variant["variant_id"]))

        bound_refs = self.resolution.bound_branch_refs_for_variant(
            self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
            int(current_variant["variant_id"]),
        )
        decision = AuthorityPolicy.evaluate_content_edit(branch_ref, bound_refs, content_changed=True)
        if decision.filtered:
            return self._report(
                row,
                "NOOP",
                "none",
                "filtered",
                "stay_current",
                "noop",
                variant_id=int(current_variant["variant_id"]),
                content_filtered_by_authority=True,
            )

        self.catalog.update_variant(int(current_variant["variant_id"]), merged, actor_scope=branch_ref.as_tuple(), conn=conn)
        return self._report(
            row,
            "UPDATED_BOUND_VARIANT",
            "none",
            "update",
            "stay_current",
            "applied",
            variant_id=int(current_variant["variant_id"]),
        )

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
