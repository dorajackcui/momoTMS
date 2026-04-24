from __future__ import annotations

from typing import Literal, TypedDict

from app.services.variant.records import PivotStatus


ReadLifecycleState = Literal["active", "orphan", "trashed"]


class BindingInfo(TypedDict):
    branch_ref: str
    created_at: str
    updated_at: str


class VariantSnapshot(TypedDict):
    variant_id: int
    entry_id: int
    file_name: str | None
    source: str
    translations: dict[str, str | None]
    remarks: dict[str, str | None]
    orphaned_at: str | None
    trashed_at: str | None
    pivot_status: PivotStatus
    pivot_changed_by_branch_ref: str | None
    pivot_changed_at: str | None
    pivot_reviewed_at: str | None
    created_at: str
    updated_at: str


class ScopeMember(TypedDict):
    variant_id: int
    entry_id: int
    business_key: str
    file_name: str | None
    source: str
    translations: dict[str, str | None]
    remarks: dict[str, str | None]
    bindings: list[BindingInfo]
    state: Literal["active", "orphan"]
    orphaned_at: str | None
    pivot_status: PivotStatus
    pivot_changed_by_branch_ref: str | None
    pivot_changed_at: str | None
    pivot_reviewed_at: str | None
    created_at: str
    updated_at: str


class LiveVariantRow(ScopeMember):
    pass


class HistoryCandidate(TypedDict):
    variant_id: int
    entry_id: int
    business_key: str
    file_name: str | None
    source: str
    translations: dict[str, str | None]
    remarks: dict[str, str | None]
    bindings: list[BindingInfo]
    state: ReadLifecycleState
    orphaned_at: str | None
    trashed_at: str | None
    pivot_status: PivotStatus
    pivot_changed_by_branch_ref: str | None
    pivot_changed_at: str | None
    pivot_reviewed_at: str | None
    created_at: str
    updated_at: str


class EntryTimelineItem(TypedDict):
    variant_id: int
    file_name: str | None
    source: str
    translations: dict[str, str | None]
    remarks: dict[str, str | None]
    bindings: list[BindingInfo]
    is_orphaned: bool
    is_trashed: bool
    orphaned_at: str | None
    trashed_at: str | None
    pivot_status: PivotStatus
    pivot_changed_by_branch_ref: str | None
    pivot_changed_at: str | None
    pivot_reviewed_at: str | None
    created_at: str
    updated_at: str


class BranchEntryView(TypedDict):
    variant_id: int
    entry_id: int
    project_id: int
    business_key: str
    file_name: str | None
    source: str
    translations: dict[str, str | None]
    remarks: dict[str, str | None]
    bindings: list[BindingInfo]
    trashed_at: str | None
    created_at: str
    updated_at: str


class FillCandidate(TypedDict):
    business_key: str
    source: str
    target_text: str
    variant_id: int
    orphaned_at: str | None
    trashed_at: str | None
    updated_at: str


class ProjectionRow(TypedDict):
    branch_ref: str
    scope_type: str
    scope_value: str
    version_series: str | None
    entry_id: int | None
    project_id: int
    business_key: str
    variant_id: int | None
    file_name: str
    source: str
    lang_target_text: str
    translations_fingerprint: str
    remarks_fingerprint: str
