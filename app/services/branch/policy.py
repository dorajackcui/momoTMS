from __future__ import annotations

from dataclasses import dataclass

from app.services.branch.models import BranchRef, DEV_SERIES_AUTHORITY


@dataclass(frozen=True, order=True)
class AuthorityKey:
    tier: int
    series_rank: int
    version_parts: tuple[int, int, int]


class AuthorityPolicy:
    @classmethod
    def key_for_branch(cls, branch_ref: BranchRef) -> AuthorityKey:
        if branch_ref.is_rel:
            return AuthorityKey(2, 0, (0, 0, 0))
        version_series = branch_ref.version_series
        if version_series is None:
            raise ValueError(f"dev branch is missing version series: {branch_ref}")
        return AuthorityKey(
            1,
            DEV_SERIES_AUTHORITY[version_series],
            branch_ref.version_parts or (0, 0, 0),
        )

    @classmethod
    def can_mutate_variant(cls, actor_branch_ref: BranchRef, bound_branch_refs: list[BranchRef]) -> bool:
        if not bound_branch_refs:
            return True
        actor_key = cls.key_for_branch(actor_branch_ref)
        highest_bound = max(cls.key_for_branch(branch_ref) for branch_ref in bound_branch_refs)
        return actor_key >= highest_bound


@dataclass(frozen=True)
class BranchMutationPolicy:
    branch_ref: BranchRef

    @classmethod
    def for_branch(cls, branch_ref: BranchRef) -> BranchMutationPolicy:
        if branch_ref.is_rel:
            return ReleaseBranchPolicy(branch_ref)
        return DevBranchPolicy(branch_ref)

    def validate_input_kind(self, input_kind: str) -> None:
        if input_kind != "direct":
            raise ValueError(f"{self.branch_ref} only supports direct mutations")

    def allow_missing_entry_creation(self) -> bool:
        return False

    def can_update_hit_variant(self, actor_branch_ref: BranchRef, bound_branch_refs: list[BranchRef]) -> bool:
        return AuthorityPolicy.can_mutate_variant(actor_branch_ref, bound_branch_refs)


@dataclass(frozen=True)
class ReleaseBranchPolicy(BranchMutationPolicy):
    pass


@dataclass(frozen=True)
class DevBranchPolicy(BranchMutationPolicy):
    def validate_input_kind(self, input_kind: str) -> None:
        if input_kind not in {"direct", "import_batch"}:
            raise ValueError(f"unsupported mutation input kind: {input_kind}")

    def allow_missing_entry_creation(self) -> bool:
        return True

    def can_update_hit_variant(self, actor_branch_ref: BranchRef, bound_branch_refs: list[BranchRef]) -> bool:
        return AuthorityPolicy.can_mutate_variant(actor_branch_ref, bound_branch_refs)


@dataclass(frozen=True)
class BranchReplacePolicy:
    source_branch_ref: BranchRef
    target_branch_ref: BranchRef

    @classmethod
    def for_branches(cls, source_branch_ref: BranchRef, target_branch_ref: BranchRef) -> BranchReplacePolicy:
        if source_branch_ref.is_dev and target_branch_ref.is_rel:
            return DevToReleaseReplacePolicy(source_branch_ref, target_branch_ref)
        raise ValueError(f"unsupported branch replace pair: {source_branch_ref} -> {target_branch_ref}")

    def cleanup_branch_refs(self, branch_service, project_id: int) -> list[BranchRef]:
        return []


@dataclass(frozen=True)
class DevToReleaseReplacePolicy(BranchReplacePolicy):
    def cleanup_branch_refs(self, branch_service, project_id: int) -> list[BranchRef]:
        branch = branch_service.get_dev_branch(self.source_branch_ref.branch_value, project_id)
        return [
            branch_service.dev_branch(version)
            for version in branch_service.versions_in_series(branch["version_series"], project_id)
        ]
