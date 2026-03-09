from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.variant.services import (
    EntryService,
    ScopeBindingService,
    VariantCatalogService,
    VariantLifecycleService,
)


class VariantInspectionService:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.entries = EntryService()
        self.bindings = ScopeBindingService()
        self.catalog = VariantCatalogService()
        self.lifecycle = VariantLifecycleService()

    def entry_variants(
        self,
        business_key: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        entry = self.entries.get_entry(business_key, project_id=project_id)
        if entry is None:
            raise KeyError(f"entry not found: {business_key}")

        binding_rows = self.bindings.list_bindings_for_entry(int(entry["entry_id"]))
        bindings_by_variant: dict[int, list[dict[str, Any]]] = {}
        for binding in binding_rows:
            bindings_by_variant.setdefault(int(binding["variant_id"]), []).append(
                {
                    "scope_type": binding["scope_type"],
                    "scope_value": binding["scope_value"],
                    "created_at": binding["created_at"],
                    "updated_at": binding["updated_at"],
                }
            )

        variants = []
        for variant in self.catalog.list_variants(int(entry["entry_id"]), include_trashed=True):
            variants.append(
                {
                    "variant_id": int(variant["variant_id"]),
                    "file_name": variant["file_name"],
                    "source": variant["source"],
                    "translations": variant["translations"],
                    "remarks": variant["remarks"],
                    "bindings": sorted(
                        bindings_by_variant.get(int(variant["variant_id"]), []),
                        key=lambda item: (item["scope_type"], item["scope_value"]),
                    ),
                    "is_orphaned": variant["orphaned_at"] is not None,
                    "is_trashed": variant["trashed_at"] is not None,
                    "orphaned_at": variant["orphaned_at"],
                    "trashed_at": variant["trashed_at"],
                    "trash_until": variant["trash_until"],
                    "restored_at": variant["restored_at"],
                    "created_at": variant["created_at"],
                    "updated_at": variant["updated_at"],
                }
            )

        return {
            "project_id": int(entry["project_id"]),
            "entry_id": int(entry["entry_id"]),
            "business_key": entry["business_key"],
            "variants": sorted(variants, key=lambda item: item["variant_id"]),
        }

    def orphan_variants(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        self.projects.require_project(project_id)
        results = []
        for item in self.lifecycle.list_orphaned_entries(project_id):
            variant = item["variant"]
            if variant["orphaned_at"] is None:
                continue
            results.append(
                {
                    "project_id": int(item["project_id"]),
                    "entry_id": int(item["entry_id"]),
                    "business_key": item["business_key"],
                    "variant_id": int(variant["variant_id"]),
                    "file_name": variant["file_name"],
                    "source": variant["source"],
                    "translations": variant["translations"],
                    "remarks": variant["remarks"],
                    "orphaned_at": variant["orphaned_at"],
                    "updated_at": variant["updated_at"],
                }
            )
        return {"project_id": project_id, "results": results}
