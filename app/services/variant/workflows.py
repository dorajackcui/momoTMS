from __future__ import annotations

from app.services.branch.models import BranchRef
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.io import normalize_non_content_value
from app.services.variant.services import EntryService, ScopeBindingService, VariantCatalogService, VariantLifecycleService


class VariantWorkflowService:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.entries = EntryService()
        self.bindings = ScopeBindingService()
        self.catalog = VariantCatalogService()
        self.lifecycle = VariantLifecycleService()

    def delete(
        self,
        branch_ref: BranchRef,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, list[dict[str, object]] | dict[str, int]]:
        self.projects.require_project(project_id)
        trashed_variant_count = 0
        removed_binding_count = 0
        not_bound_count = 0
        missing_count = 0
        report_rows: list[dict[str, object]] = []
        for business_key in self._normalize_business_keys(business_keys):
            entry = self.entries.get_entry(business_key, project_id=project_id)
            if entry is None:
                missing_count += 1
                report_rows.append({"business_key": business_key, "status": "MISSING"})
                continue
            binding = self.bindings.get_binding(int(entry["entry_id"]), branch_ref)
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
            self.bindings.remove_binding(int(entry["entry_id"]), branch_ref)
            if self.bindings.bindings.count_for_variant(variant_id) == 0:
                self.lifecycle.trash_variant(variant_id, int(entry["entry_id"]), trash_days=30)
                trashed_variant_count += 1
                report_rows.append(
                    {
                        "business_key": business_key,
                        "branch_ref": str(branch_ref),
                        "variant_id": variant_id,
                        "status": "TRASHED_VARIANT",
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
            "trashed_variant_count": trashed_variant_count,
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
        for variant_id in self._normalize_variant_ids(variant_ids):
            try:
                variant = self.catalog.get_variant(variant_id)
            except KeyError:
                missing_count += 1
                report_rows.append({"variant_id": variant_id, "status": "MISSING"})
                continue
            entry = self.entries.get_entry_by_id(int(variant["entry_id"]))
            if entry is None or int(entry["project_id"]) != project_id:
                missing_count += 1
                report_rows.append({"variant_id": variant_id, "status": "MISSING"})
                continue
            if variant["trashed_at"] is None:
                not_trashed_count += 1
                report_rows.append({"variant_id": variant_id, "status": "NOT_TRASHED"})
                continue
            restored = self.lifecycle.restore_variant(variant_id, int(entry["entry_id"]))
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

    def _normalize_business_keys(self, business_keys: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in business_keys:
            item = normalize_non_content_value(value)
            if not item or item in seen:
                continue
            seen.add(item)
            normalized.append(item)
        return normalized

    def _normalize_variant_ids(self, variant_ids: list[int]) -> list[int]:
        normalized: list[int] = []
        seen: set[int] = set()
        for value in variant_ids:
            try:
                variant_id = int(value)
            except (TypeError, ValueError):
                continue
            if variant_id <= 0 or variant_id in seen:
                continue
            seen.add(variant_id)
            normalized.append(variant_id)
        return normalized
