from __future__ import annotations

from dataclasses import dataclass

from app.services.branch.models import ScopeRef


@dataclass(frozen=True)
class ScopeMutationPolicy:
    scope_ref: ScopeRef

    @classmethod
    def for_scope(cls, scope_ref: ScopeRef) -> ScopeMutationPolicy:
        if scope_ref.is_rel:
            return ReleaseScopePolicy(scope_ref)
        return DevScopePolicy(scope_ref)

    def validate_input_kind(self, input_kind: str) -> None:
        if input_kind != "direct":
            raise ValueError(f"{self.scope_ref} only supports direct mutations")

    def allow_missing_entry_creation(self) -> bool:
        return False

    def can_update_hit_variant(self, *, rel_bound: bool) -> bool:
        return True


@dataclass(frozen=True)
class ReleaseScopePolicy(ScopeMutationPolicy):
    pass


@dataclass(frozen=True)
class DevScopePolicy(ScopeMutationPolicy):
    def validate_input_kind(self, input_kind: str) -> None:
        if input_kind not in {"direct", "import_batch"}:
            raise ValueError(f"unsupported mutation input kind: {input_kind}")

    def allow_missing_entry_creation(self) -> bool:
        return True

    def can_update_hit_variant(self, *, rel_bound: bool) -> bool:
        return not rel_bound


@dataclass(frozen=True)
class ScopeSyncPolicy:
    source_scope_ref: ScopeRef
    target_scope_ref: ScopeRef

    @classmethod
    def for_scopes(cls, source_scope_ref: ScopeRef, target_scope_ref: ScopeRef) -> ScopeSyncPolicy:
        if source_scope_ref.is_dev and target_scope_ref.is_rel:
            return DevToReleaseSyncPolicy(source_scope_ref, target_scope_ref)
        raise ValueError(f"unsupported scope sync pair: {source_scope_ref} -> {target_scope_ref}")

    def cleanup_scope_refs(self, branch_service, project_id: int) -> list[ScopeRef]:
        return []


@dataclass(frozen=True)
class DevToReleaseSyncPolicy(ScopeSyncPolicy):
    def cleanup_scope_refs(self, branch_service, project_id: int) -> list[ScopeRef]:
        branch = branch_service.get_dev_branch(self.source_scope_ref.scope_value, project_id)
        return [
            branch_service.dev_scope(version)
            for version in branch_service.versions_in_line(branch["version_line"], project_id)
        ]
