from __future__ import annotations

from typing import Any

from app.services.branch.models import BranchRef
from app.services.branch.queries import BranchQueryRepository
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.hydration import EntryVariantViewAssembler, ScopeEntryHydrator
from app.services.branch.registry import BranchRegistryService
from app.services.variant.bindings import BindingLookupService


class BranchDetailService:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.binding_lookup = BindingLookupService()
        self.branch_queries = BranchQueryRepository()
        self.scope_entry_hydrator = ScopeEntryHydrator()
        self.assembler = EntryVariantViewAssembler()
        self.registry = BranchRegistryService()

    def release_branch(self) -> BranchRef:
        return BranchRef.rel_current()

    def dev_branch(self, version: str) -> BranchRef:
        return BranchRef.dev(version)

    def get_dev_branch(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        self.projects.require_project(project_id)
        for branch in self.registry.list_dev_branches(project_id=project_id, active_only=False, skip_project_check=True):
            if branch["version"] == version:
                branch["entries"] = self.list_branch_entries(self.dev_branch(version), project_id)
                return branch
        raise KeyError(f"dev branch not found: {version}")

    def get_candidate_dev_branch(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        active_branches: list[dict[str, Any]] | None = None,
        skip_project_check: bool = False,
    ) -> dict[str, Any] | None:
        if not skip_project_check:
            self.projects.require_project(project_id)
        branches = (
            active_branches
            if active_branches is not None
            else self.registry.list_dev_branches(project_id=project_id, skip_project_check=True)
        )
        for branch in branches:
            if branch["is_candidate_release"]:
                branch_detail = dict(branch)
                branch_detail["entries"] = self.list_branch_entries(self.dev_branch(branch["version"]), project_id)
                return branch_detail
        return None

    def list_branch_entries(
        self,
        branch_ref: BranchRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> list[dict[str, Any]]:
        scope_type, scope_value = branch_ref.as_tuple()
        rows = self.branch_queries.list_scope_rows(project_id, scope_type, scope_value)
        results = self.scope_entry_hydrator.hydrate(rows)
        bindings_by_entry = self.binding_lookup.list_bindings_for_entries([int(item["entry_id"]) for item in results])
        return [
            self.assembler.assemble(
                item,
                [
                    binding
                    for binding in bindings_by_entry.get(int(item["entry_id"]), [])
                    if int(binding["variant_id"]) == int(item["variant"]["variant_id"])
                ],
            )
            for item in results
        ]
