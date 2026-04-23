from __future__ import annotations

from app.db import get_conn
from app.services.branch.models import BranchRef
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.variant.bindings import BindingCommandService, BindingLookupService
from app.services.variant.entries import EntryService
from app.services.variant.lifecycle import VariantLifecycleService
from app.services.variant.normalization import normalize_business_keys, normalize_variant_ids
from app.services.variant.catalog import VariantCatalogService


class TrashRestoreService:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.entries = EntryService()
        self.binding_commands = BindingCommandService()
        self.binding_lookup = BindingLookupService()
        self.catalog = VariantCatalogService()
        self.lifecycle = VariantLifecycleService(binding_lookup=self.binding_lookup)

    def delete(
        self,
        branch_ref: BranchRef,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, list[dict[str, object]] | dict[str, int]]:
        self.projects.require_project(project_id)
        orphaned_variant_count = 0
        removed_binding_count = 0
        not_bound_count = 0
        missing_count = 0
        report_rows: list[dict[str, object]] = []
        with get_conn() as conn:
            for business_key in normalize_business_keys(business_keys):
                entry = self.entries.get_entry(business_key, project_id=project_id, conn=conn)
                if entry is None:
                    missing_count += 1
                    report_rows.append({"business_key": business_key, "status": "MISSING"})
                    continue
                binding = self.binding_lookup.get_binding(int(entry["entry_id"]), branch_ref, conn=conn)
                if binding is None:
                    not_bound_count += 1
                    report_rows.append(
                        {
                            "business_key": business_key,
                            "branch_ref": str(branch_ref),
                            "status": "NOT_BOUND_IN_SCOPE",
                        }
                    )
                    continue
                variant_id = int(binding["variant_id"])
                self.binding_commands.remove_binding(int(entry["entry_id"]), branch_ref, conn=conn)
                self.lifecycle.refresh_orphan_states(int(entry["entry_id"]), conn=conn)
                if self.binding_lookup.count_variant_bindings(variant_id, conn=conn) == 0:
                    orphaned_variant_count += 1
                    report_rows.append(
                        {
                            "business_key": business_key,
                            "branch_ref": str(branch_ref),
                            "variant_id": variant_id,
                            "status": "ORPHANED_VARIANT",
                        }
                    )
                else:
                    removed_binding_count += 1
                    report_rows.append(
                        {
                            "business_key": business_key,
                            "branch_ref": str(branch_ref),
                            "variant_id": variant_id,
                            "status": "REMOVED_BINDING",
                        }
                    )
        summary = {
            "branch_ref": str(branch_ref),
            "orphaned_variant_count": orphaned_variant_count,
            "removed_binding_count": removed_binding_count,
            "not_bound_count": not_bound_count,
            "missing_count": missing_count,
        }
        return {"summary": summary, "report_rows": report_rows}

    def restore(
        self,
        variant_ids: list[int],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, list[dict[str, object]] | dict[str, int]]:
        self.projects.require_project(project_id)
        restored_count = 0
        source_conflict_count = 0
        not_trashed_count = 0
        missing_count = 0
        report_rows: list[dict[str, object]] = []
        with get_conn() as conn:
            for variant_id in normalize_variant_ids(variant_ids):
                try:
                    variant = self.catalog.get_variant(variant_id, conn=conn)
                except KeyError:
                    missing_count += 1
                    report_rows.append({"variant_id": variant_id, "status": "MISSING"})
                    continue
                entry = self.entries.get_entry_by_id(int(variant["entry_id"]), conn=conn)
                if entry is None or int(entry["project_id"]) != project_id:
                    missing_count += 1
                    report_rows.append({"variant_id": variant_id, "status": "MISSING"})
                    continue
                if variant["trashed_at"] is None:
                    not_trashed_count += 1
                    report_rows.append({"variant_id": variant_id, "status": "NOT_TRASHED"})
                    continue
                restored = self.lifecycle.restore_variant(variant_id, int(entry["entry_id"]), conn=conn)
                if not restored:
                    source_conflict_count += 1
                    report_rows.append(
                        {
                            "variant_id": variant_id,
                            "business_key": entry["business_key"],
                            "status": "SOURCE_CONFLICT",
                        }
                    )
                    continue
                restored_count += 1
                report_rows.append(
                    {
                        "variant_id": variant_id,
                        "business_key": entry["business_key"],
                        "status": "RESTORED",
                    }
                )
        summary = {
            "restored_count": restored_count,
            "source_conflict_count": source_conflict_count,
            "not_trashed_count": not_trashed_count,
            "missing_count": missing_count,
        }
        return {"summary": summary, "report_rows": report_rows}
