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


class BindingRecord(TypedDict):
    scope_type: str
    scope_value: str
    entry_id: int
    variant_id: int
    created_at: str
    updated_at: str


class RetainedVariantRecord(TypedDict):
    variant_id: int
    entry_id: int
    membership_type: str
    membership_value: str
    last_active_scope_type: str
    last_active_scope_value: str
    retained_at: str
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


class PreferredEntryView(TypedDict):
    string_id: int
    entry_id: int
    project_id: int
    business_key: str
    file_name: str
    source: str
    translations: dict[str, str]
    remarks: dict[str, str]
    memberships: list[dict[str, str]]
    deleted_at: str | None
    trash_until: str | None
    restored_at: str | None
    created_at: str
    updated_at: str
