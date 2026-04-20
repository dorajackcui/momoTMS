from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.services.branch.models import BranchRef
from app.services.shared.io import normalize_non_content_value
from app.services.variant.records import PivotStatus


ProjectLiveState = Literal["active", "orphan", "all"]


@dataclass(frozen=True)
class ScopeSelector:
    scope_ref: str

    @classmethod
    def parse(cls, scope_ref: str) -> ScopeSelector:
        normalized = normalize_non_content_value(scope_ref)
        if not normalized:
            raise ValueError("scope ref is required")
        if normalized == "master":
            return cls.master()
        return cls.from_branch(BranchRef.parse(normalized))

    @classmethod
    def master(cls) -> ScopeSelector:
        return cls(scope_ref="master")

    @classmethod
    def from_branch(cls, branch_ref: BranchRef) -> ScopeSelector:
        return cls(scope_ref=str(branch_ref))

    @property
    def is_master(self) -> bool:
        return self.scope_ref == "master"

    @property
    def branch_ref(self) -> BranchRef | None:
        if self.is_master:
            return None
        return BranchRef.parse(self.scope_ref)

    def __str__(self) -> str:
        return self.scope_ref


@dataclass(frozen=True)
class VariantFilter:
    state: ProjectLiveState = "active"
    search_business_key: str | None = None
    search_source: str | None = None
    branch_refs: tuple[BranchRef, ...] = field(default_factory=tuple)
    pivot_status: PivotStatus | None = None
    pivot_changed_by_branch_ref: BranchRef | None = None

    @property
    def normalized_business_key(self) -> str:
        return normalize_non_content_value(self.search_business_key).lower()

    @property
    def normalized_source(self) -> str:
        return normalize_non_content_value(self.search_source).lower()


@dataclass(frozen=True)
class HistorySelector:
    business_key: str | None = None
    source: str | None = None
    lang: str | None = None

    @classmethod
    def same_source(cls, business_key: str, source: str) -> HistorySelector:
        return cls(
            business_key=normalize_non_content_value(business_key),
            source=normalize_non_content_value(source),
        )

    @classmethod
    def fill(cls, lang: str) -> HistorySelector:
        normalized = normalize_non_content_value(lang)
        if not normalized:
            raise ValueError("lang is required")
        return cls(lang=normalized)
