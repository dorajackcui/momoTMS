from __future__ import annotations

from typing import Any, Generator

from app.db import get_conn
from app.services.branch.direct_mutation import DirectMutationApplier
from app.services.branch.import_batch_mutation import ImportBatchMutationApplier
from app.services.branch.models import BranchRef
from app.services.branch.policy import BranchMutationPolicy
from app.services.branch.registry import BranchRegistryService
from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.variant.bindings import BindingCommandService, BindingLookupService
from app.services.variant.entries import EntryService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.state_coordinator import VariantStateCoordinator
from app.services.branch.variant_resolution import VariantResolutionService


class BranchMutationService:
    def __init__(self) -> None:
        self.branch_registry = BranchRegistryService()
        self.entries = EntryService()
        self.catalog = VariantCatalogService()
        self.binding_commands = BindingCommandService()
        self.binding_lookup = BindingLookupService()
        self.bindings = VariantStateCoordinator(
            binding_commands=self.binding_commands,
            binding_lookup=self.binding_lookup,
        )
        self.imports = ImportService()
        self.projects = ProjectService()
        self.resolution = VariantResolutionService(catalog=self.catalog)
        self.direct = DirectMutationApplier(
            entries=self.entries,
            catalog=self.catalog,
            bindings=self.bindings,
            binding_lookup=self.binding_lookup,
            projects=self.projects,
            resolution=self.resolution,
        )
        self.import_batch = ImportBatchMutationApplier(
            imports=self.imports,
            entries=self.entries,
            catalog=self.catalog,
            bindings=self.bindings,
            binding_lookup=self.binding_lookup,
            resolution=self.resolution,
        )

    def apply(
        self,
        branch_ref: BranchRef,
        input_payload: dict[str, Any],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        policy = BranchMutationPolicy.for_branch(branch_ref)
        input_kind = str(input_payload["kind"])
        policy.validate_input_kind(input_kind)
        with get_conn() as conn:
            dev_branch = None
            if branch_ref.is_dev:
                mark_as_candidate = input_payload.get("mark_as_candidate_release")
                dev_branch = self.branch_registry.ensure_dev_branch(
                    branch_ref.branch_value,
                    mark_as_candidate,
                    project_id,
                    conn=conn,
                )
            if input_kind == "direct":
                return self.direct.apply(branch_ref, input_payload["changes"], policy, project_id, conn=conn)
            return self.import_batch.apply(
                branch_ref,
                int(input_payload["import_batch_id"]),
                bool(input_payload.get("mark_as_candidate_release", True)),
                project_id,
                conn=conn,
                version_series=(dev_branch or {}).get("version_series"),
            )

    def apply_streaming(
        self,
        branch_ref: BranchRef,
        input_payload: dict[str, Any],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> Generator[dict[str, Any], None, dict[str, Any]]:
        self.projects.require_project(project_id)
        policy = BranchMutationPolicy.for_branch(branch_ref)
        input_kind = str(input_payload["kind"])
        policy.validate_input_kind(input_kind)
        if input_kind != "import_batch":
            raise ValueError(f"streaming mutation is only supported for import_batch: {input_kind}")
        with get_conn() as conn:
            dev_branch = None
            if branch_ref.is_dev:
                mark_as_candidate = input_payload.get("mark_as_candidate_release")
                dev_branch = self.branch_registry.ensure_dev_branch(
                    branch_ref.branch_value,
                    mark_as_candidate,
                    project_id,
                    conn=conn,
                )
            result = yield from self.import_batch.iter_apply(
                branch_ref,
                int(input_payload["import_batch_id"]),
                bool(input_payload.get("mark_as_candidate_release", True)),
                project_id,
                conn=conn,
                version_series=(dev_branch or {}).get("version_series"),
            )
            return result
