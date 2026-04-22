from __future__ import annotations

from collections import Counter
from typing import Any

from app.db import get_conn
from app.services.branch.models import BranchRef
from app.services.branch.preview_contract import EffectPreviewSummaryBuilder, effect_forecast_row
from app.services.branch.policy import AuthorityPolicy, BranchMutationPolicy
from app.services.branch.variant_resolution import VariantResolutionService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.io import normalize_non_content_value
from app.services.variant.bindings import BindingLookupService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService


class MutationPreviewService:
    def __init__(
        self,
        *,
        entries: EntryService | None = None,
        catalog: VariantCatalogService | None = None,
        binding_lookup: BindingLookupService | None = None,
        projects: ProjectService | None = None,
        resolution: VariantResolutionService | None = None,
    ) -> None:
        self.entries = entries or EntryService()
        self.catalog = catalog or VariantCatalogService()
        self.binding_lookup = binding_lookup or BindingLookupService()
        self.projects = projects or ProjectService()
        self.resolution = resolution or VariantResolutionService(catalog=self.catalog)

    def preview(
        self,
        branch_ref: BranchRef,
        input_payload: dict[str, Any],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        policy = BranchMutationPolicy.for_branch(branch_ref)
        input_kind = str(input_payload["kind"])
        policy.validate_input_kind(input_kind)
        if input_kind != "direct":
            raise ValueError(f"mutation preview only supports direct input: {input_kind}")
        with get_conn() as conn:
            rows = self._preview_direct(
                branch_ref,
                list(input_payload.get("changes") or []),
                policy,
                project_id,
                conn,
            )
        summary_builder = EffectPreviewSummaryBuilder()
        for row in rows:
            summary_builder.add_row(row)
        return {
            "preview_kind": "effect_forecast",
            "workflow_kind": "branch_mutation",
            "request_echo": {
                "branch_ref": str(branch_ref),
                "input_kind": input_kind,
            },
            "summary": summary_builder.as_dict(),
            "rows": rows,
        }

    def _preview_direct(
        self,
        branch_ref: BranchRef,
        changes: list[dict[str, Any]],
        policy: BranchMutationPolicy,
        project_id: int,
        conn,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for change in changes:
            rows.append(self._preview_change(branch_ref, change, policy, project_id, conn))
        return rows

    def _preview_change(
        self,
        branch_ref: BranchRef,
        change: dict[str, Any],
        policy: BranchMutationPolicy,
        project_id: int,
        conn,
    ) -> dict[str, Any]:
        business_key = normalize_non_content_value(change.get("business_key"))
        if not business_key:
            return effect_forecast_row(
                {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "status": "INVALID_ROW",
                },
                binding_effect="none",
                variant_resolution="stay_current",
                row_outcome="invalid",
            )
        for lang in (change.get("translations_by_lang") or {}).keys():
            self.projects.require_language(lang, project_id)

        entry = self.entries.get_entry(business_key, project_id=project_id, conn=conn)
        current_binding = None
        current_variant = None
        if entry is not None:
            entry_id = int(entry["entry_id"])
            current_binding = self.binding_lookup.get_binding(entry_id, branch_ref, conn=conn)
            current_variant = (
                self.catalog.get_variant(int(current_binding["variant_id"]), conn=conn)
                if current_binding is not None
                else None
            )
        else:
            entry_id = None

        if change.get("source") is None:
            if current_variant is None:
                return effect_forecast_row(
                    {
                        "business_key": business_key,
                        "branch_ref": str(branch_ref),
                        "status": "MISSING_IN_SCOPE",
                    },
                    binding_effect="none",
                    variant_resolution="stay_current",
                    row_outcome="missing",
                )
            merged = self.resolution.merged_variant_payload(current_variant, change, current_variant["source"])
            if self.resolution.variant_matches(current_variant, merged):
                return effect_forecast_row(
                    {
                        "business_key": business_key,
                        "branch_ref": str(branch_ref),
                        "variant_id": int(current_variant["variant_id"]),
                        "status": "NOOP",
                    },
                    binding_effect="none",
                    variant_resolution="stay_current",
                    row_outcome="noop",
                )
            bound_branch_refs = self.resolution.bound_branch_refs_for_variant(
                self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
                int(current_variant["variant_id"]),
            )
            decision = AuthorityPolicy.evaluate_content_edit(
                branch_ref,
                bound_branch_refs,
                content_changed=not self.resolution.variant_matches(current_variant, merged),
            )
            if decision.filtered:
                return effect_forecast_row(
                    {
                        "business_key": business_key,
                        "branch_ref": str(branch_ref),
                        "variant_id": int(current_variant["variant_id"]),
                        "status": "NOOP",
                        "content_filtered_by_authority": True,
                    },
                    binding_effect="none",
                    variant_resolution="stay_current",
                    row_outcome="noop",
                )
            return effect_forecast_row(
                {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": int(current_variant["variant_id"]),
                    "status": "UPDATED_BOUND_VARIANT",
                },
                binding_effect="none",
                variant_resolution="stay_current",
                row_outcome="applied",
            )

        requested_source = normalize_non_content_value(change.get("source"))
        if not requested_source:
            return effect_forecast_row(
                {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "status": "INVALID_ROW",
                },
                binding_effect="none",
                variant_resolution="stay_current",
                row_outcome="invalid",
            )

        if current_variant is not None and requested_source == current_variant["source"]:
            merged = self.resolution.merged_variant_payload(current_variant, change, requested_source)
            if self.resolution.variant_matches(current_variant, merged):
                return effect_forecast_row(
                    {
                        "business_key": business_key,
                        "branch_ref": str(branch_ref),
                        "variant_id": int(current_variant["variant_id"]),
                        "status": "NOOP",
                    },
                    binding_effect="none",
                    variant_resolution="stay_current",
                    row_outcome="noop",
                )
            bound_branch_refs = self.resolution.bound_branch_refs_for_variant(
                self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
                int(current_variant["variant_id"]),
            )
            decision = AuthorityPolicy.evaluate_content_edit(
                branch_ref,
                bound_branch_refs,
                content_changed=True,
            )
            if decision.filtered:
                return effect_forecast_row(
                    {
                        "business_key": business_key,
                        "branch_ref": str(branch_ref),
                        "variant_id": int(current_variant["variant_id"]),
                        "status": "NOOP",
                        "content_filtered_by_authority": True,
                    },
                    binding_effect="none",
                    variant_resolution="stay_current",
                    row_outcome="noop",
                )
            return effect_forecast_row(
                {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": int(current_variant["variant_id"]),
                    "status": "UPDATED_BOUND_VARIANT",
                },
                binding_effect="none",
                variant_resolution="stay_current",
                row_outcome="applied",
            )

        target_variant = self.catalog.find_variant_by_source(
            entry_id,
            requested_source,
            include_trashed=False,
            conn=conn,
        ) if entry_id is not None else None
        content_base = target_variant or current_variant
        merged = self.resolution.merged_variant_payload(content_base, change, requested_source)
        if target_variant is None:
            if current_variant is None and not policy.allow_missing_entry_creation():
                return effect_forecast_row(
                    {
                        "business_key": business_key,
                        "branch_ref": str(branch_ref),
                        "status": "MISSING_IN_SCOPE",
                    },
                    binding_effect="none",
                    variant_resolution="stay_current",
                    row_outcome="missing",
                )
            return effect_forecast_row(
                {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "status": "CREATED_AND_BOUND_VARIANT",
                },
                binding_effect="bind" if current_binding is None else "rebind",
                variant_resolution="create_new",
                row_outcome="applied",
            )

        target_variant_id = int(target_variant["variant_id"])
        current_matches_target = current_binding is not None and int(current_binding["variant_id"]) == target_variant_id
        bound_branch_refs = self.resolution.bound_branch_refs_for_variant(
            self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
            target_variant_id,
        )
        payload_matches_target = self.resolution.variant_matches(target_variant, merged)
        decision = AuthorityPolicy.evaluate_content_edit(
            branch_ref,
            bound_branch_refs,
            content_changed=not payload_matches_target,
        )
        if decision.filtered:
            if current_matches_target:
                return effect_forecast_row(
                    {
                        "business_key": business_key,
                        "branch_ref": str(branch_ref),
                        "variant_id": target_variant_id,
                        "status": "NOOP",
                        "content_filtered_by_authority": True,
                    },
                    binding_effect="none",
                    variant_resolution="stay_current",
                    row_outcome="noop",
                )
            return effect_forecast_row(
                {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": target_variant_id,
                    "status": "BOUND_EXISTING_VARIANT",
                    "content_filtered_by_authority": True,
                },
                binding_effect="bind" if current_binding is None else "rebind",
                variant_resolution="reuse_existing",
                row_outcome="applied",
            )
        if current_matches_target and payload_matches_target:
            return effect_forecast_row(
                {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": target_variant_id,
                    "status": "NOOP",
                },
                binding_effect="none",
                variant_resolution="stay_current",
                row_outcome="noop",
            )
        if payload_matches_target:
            return effect_forecast_row(
                {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": target_variant_id,
                    "status": "BOUND_EXISTING_VARIANT",
                },
                binding_effect="bind" if current_binding is None else "rebind",
                variant_resolution="reuse_existing",
                row_outcome="applied",
            )

        if current_matches_target:
            return effect_forecast_row(
                {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": target_variant_id,
                    "status": "UPDATED_BOUND_VARIANT",
                },
                binding_effect="none",
                variant_resolution="stay_current",
                row_outcome="applied",
            )
        return effect_forecast_row(
            {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": target_variant_id,
                "status": "UPDATED_AND_BOUND_EXISTING_VARIANT",
            },
            binding_effect="bind" if current_binding is None else "rebind",
            variant_resolution="reuse_existing",
            row_outcome="applied",
        )
