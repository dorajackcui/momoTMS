from __future__ import annotations

from app.db import get_conn
from app.services.branch.models import BranchRef
from app.services.branch.policy import AuthorityPolicy
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.variant.bindings import BindingLookupService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.normalization import normalize_variant_ids
from app.services.variant.pivot import PIVOT_STATUS_CHANGED, VariantPivotCoordinator, pivot_changed_by_branch_ref


class PivotReviewService:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.entries = EntryService()
        self.binding_lookup = BindingLookupService()
        self.catalog = VariantCatalogService()
        self.pivot = VariantPivotCoordinator()

    def review(
        self,
        branch_ref: BranchRef,
        variant_ids: list[int],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, list[dict[str, object]] | dict[str, int] | str]:
        self.projects.require_project(project_id)
        reviewed_count = 0
        not_changed_count = 0
        not_visible_count = 0
        forbidden_count = 0
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

                if variant["pivot_status"] != PIVOT_STATUS_CHANGED:
                    not_changed_count += 1
                    report_rows.append(
                        {
                            "variant_id": variant_id,
                            "business_key": entry["business_key"],
                            "status": "NOT_CHANGED",
                        }
                    )
                    continue

                if not self._variant_visible_in_scope(int(entry["entry_id"]), variant_id, branch_ref, conn=conn):
                    not_visible_count += 1
                    report_rows.append(
                        {
                            "variant_id": variant_id,
                            "business_key": entry["business_key"],
                            "branch_ref": str(branch_ref),
                            "status": "NOT_VISIBLE_IN_SCOPE",
                        }
                    )
                    continue

                changed_owner_ref = pivot_changed_by_branch_ref(variant)
                if changed_owner_ref is None:
                    raise RuntimeError(f"changed pivot variant is missing owner metadata: {variant_id}")
                changed_owner = BranchRef.parse(changed_owner_ref)
                if AuthorityPolicy.key_for_branch(branch_ref) < AuthorityPolicy.key_for_branch(changed_owner):
                    forbidden_count += 1
                    report_rows.append(
                        {
                            "variant_id": variant_id,
                            "business_key": entry["business_key"],
                            "branch_ref": str(branch_ref),
                            "pivot_changed_by_branch_ref": changed_owner_ref,
                            "status": "FORBIDDEN_BY_AUTHORITY",
                        }
                    )
                    continue

                self.pivot.review_variant(variant_id=variant_id, conn=conn)
                reviewed_count += 1
                report_rows.append(
                    {
                        "variant_id": variant_id,
                        "business_key": entry["business_key"],
                        "branch_ref": str(branch_ref),
                        "status": "REVIEWED",
                    }
                )

        summary = {
            "branch_ref": str(branch_ref),
            "processed_count": len(report_rows),
            "reviewed_count": reviewed_count,
            "not_changed_count": not_changed_count,
            "not_visible_in_scope_count": not_visible_count,
            "forbidden_by_authority_count": forbidden_count,
            "missing_count": missing_count,
        }
        return {"summary": summary, "report_rows": report_rows}

    def _variant_visible_in_scope(
        self,
        entry_id: int,
        variant_id: int,
        branch_ref: BranchRef,
        *,
        conn,
    ) -> bool:
        binding = self.binding_lookup.get_binding(entry_id, branch_ref, conn=conn)
        return binding is not None and int(binding["variant_id"]) == variant_id
