from __future__ import annotations

from typing import Any

from app.db import get_conn
from app.services.branch.models import BranchRef
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.io import normalize_non_content_value
from app.services.variant.bindings import BindingLookupService
from app.services.variant.entries import EntryService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.repositories import VariantQueryRepository


class InspectionQueryRepository:
    def list_orphan_variant_rows(self, project_id: int) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    e.entry_id,
                    e.project_id,
                    e.business_key,
                    v.variant_id,
                    v.file_name,
                    v.source,
                    v.orphaned_at,
                    v.trashed_at,
                    v.trash_until,
                    v.restored_at,
                    v.created_at,
                    v.updated_at
                FROM variants v
                JOIN entries e ON e.entry_id = v.entry_id
                WHERE e.project_id = ?
                  AND v.orphaned_at IS NOT NULL
                  AND v.trashed_at IS NULL
                ORDER BY v.orphaned_at DESC, e.business_key, v.variant_id
                """,
                (project_id,),
            ).fetchall()
        return [
            {
                "project_id": int(row["project_id"]),
                "entry_id": int(row["entry_id"]),
                "business_key": normalize_non_content_value(row["business_key"]),
                "variant_id": int(row["variant_id"]),
                "file_name": normalize_non_content_value(row["file_name"]),
                "source": normalize_non_content_value(row["source"]),
                "orphaned_at": row["orphaned_at"],
                "trashed_at": row["trashed_at"],
                "trash_until": row["trash_until"],
                "restored_at": row["restored_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]


class InspectionReadService:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.entries = EntryService()
        self.binding_lookup = BindingLookupService()
        self.catalog = VariantCatalogService()
        self.variant_queries = VariantQueryRepository()
        self.queries = InspectionQueryRepository()

    def entry_variants(
        self,
        business_key: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        entry = self.entries.get_entry(business_key, project_id=project_id)
        if entry is None:
            raise KeyError(f"entry not found: {business_key}")

        binding_rows = self.binding_lookup.list_bindings_for_entry(int(entry["entry_id"]))
        bindings_by_variant: dict[int, list[dict[str, Any]]] = {}
        for binding in binding_rows:
            bindings_by_variant.setdefault(int(binding["variant_id"]), []).append(
                {
                    "branch_ref": str(BranchRef.parse(f"{binding['scope_type']}/{binding['scope_value']}")),
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
                        key=lambda item: item["branch_ref"],
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
        rows = self.queries.list_orphan_variant_rows(project_id)
        variants_by_id = {
            variant["variant_id"]: variant for variant in self.variant_queries.hydrate_variant_rows(rows)
        }
        results = []
        for row in rows:
            variant = variants_by_id[int(row["variant_id"])]
            results.append(
                {
                    "project_id": int(row["project_id"]),
                    "entry_id": int(row["entry_id"]),
                    "business_key": row["business_key"],
                    "variant_id": int(variant["variant_id"]),
                    "file_name": variant["file_name"],
                    "source": variant["source"],
                    "translations": variant["translations"],
                    "remarks": variant["remarks"],
                    "orphaned_at": row["orphaned_at"],
                    "updated_at": variant["updated_at"],
                }
            )
        return {"project_id": project_id, "results": results}
