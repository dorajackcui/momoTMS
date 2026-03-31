from __future__ import annotations

from collections import Counter
import sqlite3
from time import perf_counter
from typing import Any

from app.services.branch.models import BranchRef
from app.services.branch.policy import BranchMutationPolicy
from app.services.project.service import ProjectService
from app.services.shared.io import normalize_non_content_value
from app.services.variant.bindings import BindingLookupService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.state_coordinator import VariantStateCoordinator

from app.services.branch.variant_resolution import VariantResolutionService


class DirectMutationApplier:
    def __init__(
        self,
        *,
        entries: EntryService | None = None,
        catalog: VariantCatalogService | None = None,
        bindings: VariantStateCoordinator | None = None,
        binding_lookup: BindingLookupService | None = None,
        projects: ProjectService | None = None,
        resolution: VariantResolutionService | None = None,
    ) -> None:
        self.entries = entries or EntryService()
        self.catalog = catalog or VariantCatalogService()
        self.bindings = bindings or VariantStateCoordinator()
        self.binding_lookup = binding_lookup or BindingLookupService()
        self.projects = projects or ProjectService()
        self.resolution = resolution or VariantResolutionService(catalog=self.catalog)

    def apply(
        self,
        branch_ref: BranchRef,
        changes: list[dict[str, Any]],
        policy: BranchMutationPolicy,
        project_id: int,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        started = perf_counter()
        status_counts: Counter[str] = Counter()
        report_rows: list[dict[str, Any]] = []
        created_entry_count = 0
        for change in changes:
            row = self.apply_change(branch_ref, change, policy, project_id, conn=conn)
            created_entry_count += int(row.pop("created_entry", False))
            status_counts.update([row["status"]])
            report_rows.append(row)
        summary = {
            "branch_ref": str(branch_ref),
            "input_kind": "direct",
            "processed_count": len(report_rows),
            "created_entry_count": created_entry_count,
            **self._status_summary(status_counts),
            "stages": [
                {
                    "stage": "apply_scope_mutation",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {
                        "branch_ref": str(branch_ref),
                        "input_kind": "direct",
                        "processed_count": len(report_rows),
                    },
                }
            ],
        }
        return {"summary": summary, "report_rows": report_rows}

    def apply_change(
        self,
        branch_ref: BranchRef,
        change: dict[str, Any],
        policy: BranchMutationPolicy,
        project_id: int,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        business_key = normalize_non_content_value(change.get("business_key"))
        if not business_key:
            raise ValueError("business_key is required")
        for lang in (change.get("translations_by_lang") or {}).keys():
            self.projects.require_language(lang, project_id)

        entry = self.entries.get_entry(business_key, project_id=project_id, conn=conn)
        created_entry = False
        if entry is None and change.get("source") is not None and policy.allow_missing_entry_creation():
            entry = self.entries.get_or_create_entry(business_key, project_id=project_id, conn=conn)
            created_entry = True
        if entry is None:
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "status": "MISSING_IN_SCOPE",
                "created_entry": created_entry,
            }

        entry_id = int(entry["entry_id"])
        current_binding = self.binding_lookup.get_binding(entry_id, branch_ref, conn=conn)
        current_variant = (
            self.catalog.get_variant(int(current_binding["variant_id"]), conn=conn)
            if current_binding is not None
            else None
        )
        if branch_ref.is_rel and current_variant is None:
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "status": "MISSING_IN_SCOPE",
                "created_entry": created_entry,
            }

        if change.get("source") is None:
            if current_variant is None:
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "status": "MISSING_IN_SCOPE",
                    "created_entry": created_entry,
                }
            merged = self.resolution.merged_variant_payload(current_variant, change, current_variant["source"])
            if self.resolution.variant_matches(current_variant, merged):
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": int(current_variant["variant_id"]),
                    "status": "NOOP",
                    "created_entry": created_entry,
                }
            bound_branch_refs = self.resolution.bound_branch_refs_for_variant(
                self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
                int(current_variant["variant_id"]),
            )
            if not policy.can_update_hit_variant(branch_ref, bound_branch_refs):
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": int(current_variant["variant_id"]),
                    "status": "NOOP",
                    "created_entry": created_entry,
                }
            self.catalog.update_variant(
                int(current_variant["variant_id"]),
                merged,
                actor_scope=branch_ref.as_tuple(),
                conn=conn,
            )
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": int(current_variant["variant_id"]),
                "status": "UPDATED_BOUND_VARIANT",
                "created_entry": created_entry,
            }

        requested_source = normalize_non_content_value(change.get("source"))
        if not requested_source:
            raise ValueError("source is required")
        if current_variant is not None and requested_source == current_variant["source"]:
            merged = self.resolution.merged_variant_payload(current_variant, change, requested_source)
            if self.resolution.variant_matches(current_variant, merged):
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": int(current_variant["variant_id"]),
                    "status": "NOOP",
                    "created_entry": created_entry,
                }
            bound_branch_refs = self.resolution.bound_branch_refs_for_variant(
                self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
                int(current_variant["variant_id"]),
            )
            if not policy.can_update_hit_variant(branch_ref, bound_branch_refs):
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": int(current_variant["variant_id"]),
                    "status": "NOOP",
                    "created_entry": created_entry,
                }
            self.catalog.update_variant(
                int(current_variant["variant_id"]),
                merged,
                actor_scope=branch_ref.as_tuple(),
                conn=conn,
            )
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": int(current_variant["variant_id"]),
                "status": "UPDATED_BOUND_VARIANT",
                "created_entry": created_entry,
            }

        target_variant = self.catalog.find_variant_by_source(
            entry_id,
            requested_source,
            include_trashed=False,
            conn=conn,
        )
        content_base = current_variant or target_variant
        merged = self.resolution.merged_variant_payload(content_base, change, requested_source)
        if target_variant is None:
            if current_variant is None and not policy.allow_missing_entry_creation():
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "status": "MISSING_IN_SCOPE",
                    "created_entry": created_entry,
                }
            variant_id = self.catalog.create_variant(
                entry_id,
                merged,
                conn=conn,
            )
            self.bindings.bind_scope(entry_id, branch_ref, variant_id, conn=conn)
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": variant_id,
                "status": "CREATED_AND_BOUND_VARIANT",
                "created_entry": created_entry,
            }

        target_variant_id = int(target_variant["variant_id"])
        current_matches_target = current_binding is not None and int(current_binding["variant_id"]) == target_variant_id
        bound_branch_refs = self.resolution.bound_branch_refs_for_variant(
            self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
            target_variant_id,
        )
        if not policy.can_update_hit_variant(branch_ref, bound_branch_refs):
            if current_matches_target:
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": target_variant_id,
                    "status": "NOOP",
                    "created_entry": created_entry,
                }
            self.bindings.bind_scope(entry_id, branch_ref, target_variant_id, conn=conn)
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": target_variant_id,
                "status": "BOUND_EXISTING_VARIANT",
                "created_entry": created_entry,
            }

        payload_matches_target = self.resolution.variant_matches(target_variant, merged)
        if current_matches_target and payload_matches_target:
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": target_variant_id,
                "status": "NOOP",
                "created_entry": created_entry,
            }
        if payload_matches_target:
            self.bindings.bind_scope(entry_id, branch_ref, target_variant_id, conn=conn)
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": target_variant_id,
                "status": "BOUND_EXISTING_VARIANT",
                "created_entry": created_entry,
            }

        self.catalog.update_variant(
            target_variant_id,
            merged,
            actor_scope=branch_ref.as_tuple(),
            conn=conn,
        )
        if not current_matches_target:
            self.bindings.bind_scope(entry_id, branch_ref, target_variant_id, conn=conn)
            status = "UPDATED_AND_BOUND_EXISTING_VARIANT"
        else:
            status = "UPDATED_BOUND_VARIANT"
        return {
            "business_key": business_key,
            "branch_ref": str(branch_ref),
            "variant_id": target_variant_id,
            "status": status,
            "created_entry": created_entry,
        }

    def _status_summary(self, status_counts: Counter[str]) -> dict[str, int]:
        return {
            "updated_bound_variant_count": status_counts["UPDATED_BOUND_VARIANT"],
            "bound_existing_variant_count": status_counts["BOUND_EXISTING_VARIANT"],
            "updated_and_bound_existing_variant_count": status_counts["UPDATED_AND_BOUND_EXISTING_VARIANT"],
            "created_and_bound_variant_count": status_counts["CREATED_AND_BOUND_VARIANT"],
            "missing_in_scope_count": status_counts["MISSING_IN_SCOPE"],
            "noop_count": status_counts["NOOP"],
        }
