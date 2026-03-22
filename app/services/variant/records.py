from __future__ import annotations

from typing import TypedDict


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
    created_at: str
    updated_at: str


class FillCandidateRecord(TypedDict):
    business_key: str
    source: str
    target_text: str
    variant_id: int
    orphaned_at: str | None
    trashed_at: str | None
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


class BindingSummary(TypedDict):
    branch_ref: str
    created_at: str
    updated_at: str


class ScopeEntryRecord(TypedDict):
    entry_id: int
    project_id: int
    business_key: str
    variant: VariantRecord
    scope_type: str
    scope_value: str
    created_at: str
    updated_at: str


class EntryVariantView(TypedDict):
    variant_id: int
    entry_id: int
    project_id: int
    business_key: str
    file_name: str
    source: str
    translations: dict[str, str]
    remarks: dict[str, str]
    bindings: list[BindingSummary]
    trashed_at: str | None
    trash_until: str | None
    restored_at: str | None
    created_at: str
    updated_at: str
