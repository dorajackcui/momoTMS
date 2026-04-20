from __future__ import annotations

from typing import Literal, TypedDict


PivotStatus = Literal["init", "changed", "reviewed"]


class EntryRecord(TypedDict):
    entry_id: int
    project_id: int
    business_key: str
    created_at: str
    updated_at: str


class VariantRecord(TypedDict):
    variant_id: int
    entry_id: int
    file_name: str
    source: str
    translations: dict[str, str]
    remarks: dict[str, str]
    orphaned_at: str | None
    trashed_at: str | None
    trash_until: str | None
    restored_at: str | None
    pivot_status: PivotStatus
    pivot_changed_by_scope_type: str | None
    pivot_changed_by_scope_value: str | None
    pivot_changed_at: str | None
    pivot_reviewed_at: str | None
    pivot_status_updated_at: str
    created_at: str
    updated_at: str


class VariantContent(TypedDict):
    file_name: str
    source: str
    translations: dict[str, str]
    remarks: dict[str, str]


class BindingRecord(TypedDict):
    scope_type: str
    scope_value: str
    entry_id: int
    variant_id: int
    created_at: str
    updated_at: str
