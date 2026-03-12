from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
from typing import Any

from app.services.branch.models import ScopeRef
from app.services.shared.io import (
    normalize_content_map,
    normalize_non_content_map,
    normalize_non_content_value,
)
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.utils import now_iso
from app.services.variant.records import (
    BindingRecord,
    BindingSummary,
    EntryVariantView,
    EntryRecord,
    ScopeEntryRecord,
    VariantRecord,
)
from app.services.variant.repositories import (
    EntryRepository,
    ScopeBindingRepository,
    VariantRepository,
)


class EntryService:
    def __init__(self, entries: EntryRepository | None = None) -> None:
        self.entries = entries or EntryRepository()

    def get_or_create_entry(
        self,
        business_key: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> EntryRecord:
        normalized_key = self._require_non_content("business_key", business_key)
        entry = self.entries.get_by_business_key(project_id, normalized_key)
        if entry is not None:
            return entry
        return self.entries.create(project_id, normalized_key, now_iso())

    def get_entry(self, business_key: str, project_id: int = DEFAULT_PROJECT_ID) -> EntryRecord | None:
        normalized_key = self._require_non_content("business_key", business_key)
        return self.entries.get_by_business_key(project_id, normalized_key)

    def get_entry_by_id(self, entry_id: int) -> EntryRecord | None:
        return self.entries.get_by_id(entry_id)

    def ensure_entries(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, EntryRecord]:
        normalized_keys = self._normalize_business_keys(business_keys)
        if not normalized_keys:
            return {}
        existing = self.entries.get_by_keys(project_id, normalized_keys)
        missing_keys = [key for key in normalized_keys if key not in existing]
        if missing_keys:
            self.entries.insert_many_ignore(project_id, missing_keys, now_iso())
        return self.entries.get_by_keys(project_id, normalized_keys)

    def get_entries_by_keys(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, EntryRecord]:
        normalized_keys = self._normalize_business_keys(business_keys)
        return self.entries.get_by_keys(project_id, normalized_keys)

    def list_entries(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        search: str | None = None,
    ) -> list[EntryRecord]:
        return self.entries.list(project_id, search=search)

    def _require_non_content(self, field_name: str, value: Any) -> str:
        normalized = normalize_non_content_value(value)
        if not normalized:
            raise ValueError(f"{field_name} is required")
        return normalized

    def _normalize_business_keys(self, business_keys: list[str]) -> list[str]:
        normalized_keys: list[str] = []
        seen: set[str] = set()
        for value in business_keys:
            normalized = normalize_non_content_value(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            normalized_keys.append(normalized)
        return normalized_keys


class VariantCatalogService:
    def __init__(self, variants: VariantRepository | None = None) -> None:
        self.variants = variants or VariantRepository()

    def create_variant(
        self,
        entry_id: int,
        file_name: str | None,
        source: str,
        translations: dict[str, str | None],
        remarks: dict[str, str | None],
    ) -> int:
        normalized_file_name = normalize_non_content_value(file_name)
        normalized_source = self._require_non_content("source", source)
        normalized_translations = normalize_content_map(translations)
        normalized_remarks = normalize_non_content_map(remarks)
        timestamp = now_iso()
        variant_id = self.variants.create(entry_id, normalized_file_name, normalized_source, timestamp)
        self.variants.overwrite_translations(variant_id, normalized_translations, timestamp)
        self.variants.overwrite_remarks(variant_id, normalized_remarks, timestamp)
        return variant_id

    def update_variant(
        self,
        variant_id: int,
        file_name: str | None,
        source: str,
        translations: dict[str, str | None],
        remarks: dict[str, str | None],
        restore_if_trashed: bool = False,
    ) -> None:
        normalized_file_name = normalize_non_content_value(file_name)
        normalized_source = self._require_non_content("source", source)
        timestamp = now_iso()
        self.variants.update(
            variant_id,
            normalized_file_name,
            normalized_source,
            timestamp,
            restore_if_trashed=restore_if_trashed,
        )
        self.variants.overwrite_translations(variant_id, normalize_content_map(translations), timestamp)
        self.variants.overwrite_remarks(variant_id, normalize_non_content_map(remarks), timestamp)

    def replace_translations(self, variant_id: int, translations: dict[str, str | None]) -> None:
        self.variants.replace_translations(variant_id, normalize_content_map(translations), now_iso())

    def replace_remarks(self, variant_id: int, remarks: dict[str, str | None]) -> None:
        self.variants.replace_remarks(variant_id, normalize_non_content_map(remarks), now_iso())

    def get_variant(self, variant_id: int) -> VariantRecord:
        variant = self.variants.get(variant_id)
        if variant is None:
            raise KeyError(f"variant not found: {variant_id}")
        return variant

    def find_reusable_variant(
        self,
        entry_id: int,
        file_name: str | None,
        source: str,
        translations: dict[str, str | None],
        remarks: dict[str, str | None],
    ) -> VariantRecord | None:
        normalized_source = self._require_non_content("source", source)
        return self.variants.get_active_by_entry_and_source(entry_id, normalized_source)

    def find_variant_by_source(
        self,
        entry_id: int,
        source: str,
        include_trashed: bool = False,
    ) -> VariantRecord | None:
        normalized_source = self._require_non_content("source", source)
        if not include_trashed:
            return self.variants.get_active_by_entry_and_source(entry_id, normalized_source)
        matches = [
            variant
            for variant in self.list_variants(entry_id, include_trashed=True)
            if variant["source"] == normalized_source
        ]
        if not matches:
            return None
        active_matches = [variant for variant in matches if variant["trashed_at"] is None]
        if len(active_matches) > 1:
            raise RuntimeError(
                f"duplicate active variants found for entry_id={entry_id}, source={normalized_source!r}"
            )
        if active_matches:
            return active_matches[0]
        return matches[-1]

    def list_variants(self, entry_id: int, include_trashed: bool = True) -> list[VariantRecord]:
        return self.variants.list_by_entry(entry_id, include_trashed=include_trashed)

    def list_variants_for_entries(
        self,
        entry_ids: list[int],
        include_trashed: bool = True,
    ) -> dict[int, list[VariantRecord]]:
        return self.variants.list_by_entries(entry_ids, include_trashed=include_trashed)

    def _require_non_content(self, field_name: str, value: Any) -> str:
        normalized = normalize_non_content_value(value)
        if not normalized:
            raise ValueError(f"{field_name} is required")
        return normalized


class VariantLifecycleService:
    def __init__(
        self,
        variants: VariantRepository | None = None,
        bindings: ScopeBindingRepository | None = None,
    ) -> None:
        self.variants = variants or VariantRepository()
        self.bindings = bindings or ScopeBindingRepository()

    def refresh_orphan_states(
        self,
        entry_id: int,
        conn: sqlite3.Connection | None = None,
        timestamp: str | None = None,
    ) -> None:
        variant_rows = self.variants.list_by_entry(entry_id, include_trashed=True, conn=conn)
        binding_counts = self.bindings.binding_counts_for_entry(entry_id, conn=conn)
        marker = timestamp or now_iso()
        for variant in variant_rows:
            variant_id = int(variant["variant_id"])
            if variant["trashed_at"] is not None:
                orphaned_at = None
            elif binding_counts.get(variant_id, 0) == 0:
                orphaned_at = variant["orphaned_at"] or marker
            else:
                orphaned_at = None
            self.variants.set_orphaned_at(variant_id, orphaned_at, conn=conn)

    def trash_entries(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
        trash_days: int = 30,
    ) -> dict[str, list[str]]:
        if not business_keys:
            return {"deleted": [], "already_deleted": [], "missing": []}
        normalized_keys = self._normalize_business_keys(business_keys)
        counts = self.variants.counts_for_business_keys(project_id, normalized_keys)
        timestamp = now_iso()
        trash_until = self._trash_until(trash_days)
        deleted: list[str] = []
        already_deleted: list[str] = []
        for key in normalized_keys:
            row = counts.get(key)
            if row is None:
                continue
            if row["variant_count"] == 0 or row["active_variant_count"] == 0:
                already_deleted.append(key)
                continue
            self.variants.trash_entry_variants(project_id, key, timestamp, trash_until)
            deleted.append(key)
        missing = sorted(set(normalized_keys) - set(counts))
        return {
            "deleted": sorted(deleted),
            "already_deleted": sorted(already_deleted),
            "missing": missing,
        }

    def restore_entries(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, list[str]]:
        if not business_keys:
            return {"restored": [], "not_deleted": [], "missing": []}
        normalized_keys = self._normalize_business_keys(business_keys)
        counts = self.variants.counts_for_business_keys(project_id, normalized_keys)
        timestamp = now_iso()
        restored: list[str] = []
        not_deleted: list[str] = []
        refreshed_entry_ids: list[int] = []
        for key in normalized_keys:
            row = counts.get(key)
            if row is None:
                continue
            if row["variant_count"] == 0 or row["trashed_variant_count"] == 0:
                not_deleted.append(key)
                continue
            self.variants.restore_entry_variants(project_id, key, timestamp)
            restored.append(key)
            refreshed_entry_ids.append(int(row["entry_id"]))
        for entry_id in refreshed_entry_ids:
            self.refresh_orphan_states(entry_id)
        missing = sorted(set(normalized_keys) - set(counts))
        return {
            "restored": sorted(restored),
            "not_deleted": sorted(not_deleted),
            "missing": missing,
        }

    def trash_count(self, project_id: int = DEFAULT_PROJECT_ID) -> int:
        return self.variants.count_trashed_entries(project_id)

    def list_orphaned_entries(self, project_id: int = DEFAULT_PROJECT_ID) -> list[dict[str, Any]]:
        return self.variants.list_orphaned_entries(project_id)

    def trash_variant(
        self,
        variant_id: int,
        entry_id: int,
        trash_days: int = 30,
    ) -> None:
        timestamp = now_iso()
        self.variants.trash_variant(variant_id, timestamp, self._trash_until(trash_days))
        self.refresh_orphan_states(entry_id)

    def restore_variant(self, variant_id: int, entry_id: int) -> bool:
        timestamp = now_iso()
        restored = self.variants.restore_variant(variant_id, timestamp)
        if not restored:
            return False
        self.refresh_orphan_states(entry_id, timestamp=timestamp)
        return True

    def _normalize_business_keys(self, business_keys: list[str]) -> list[str]:
        normalized_keys: list[str] = []
        seen: set[str] = set()
        for value in business_keys:
            normalized = normalize_non_content_value(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            normalized_keys.append(normalized)
        return normalized_keys

    def _trash_until(self, days: int) -> str:
        return (
            datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=days)
        ).isoformat()


class ScopeBindingService:
    def __init__(
        self,
        variants: VariantRepository | None = None,
        bindings: ScopeBindingRepository | None = None,
        lifecycle: VariantLifecycleService | None = None,
    ) -> None:
        self.variants = variants or VariantRepository()
        self.bindings = bindings or ScopeBindingRepository()
        self.lifecycle = lifecycle or VariantLifecycleService(self.variants, self.bindings)

    def bind_scope(
        self,
        entry_id: int,
        scope_ref: ScopeRef,
        variant_id: int,
    ) -> None:
        scope_type, scope_value = scope_ref.as_tuple()
        timestamp = now_iso()
        self.bindings.upsert(
            entry_id,
            scope_type,
            scope_value,
            variant_id,
            timestamp,
        )
        self.variants.clear_orphaned_at(variant_id, timestamp)
        self.lifecycle.refresh_orphan_states(entry_id)

    def get_binding(self, entry_id: int, scope_ref: ScopeRef) -> BindingRecord | None:
        scope_type, scope_value = scope_ref.as_tuple()
        return self.bindings.get(entry_id, scope_type, scope_value)

    def get_bindings_for_entries(
        self,
        entry_ids: list[int],
        scope_ref: ScopeRef,
    ) -> dict[int, BindingRecord]:
        scope_type, scope_value = scope_ref.as_tuple()
        return self.bindings.get_for_entries(
            entry_ids,
            scope_type,
            scope_value,
        )

    def list_bindings_for_entry(self, entry_id: int) -> list[BindingRecord]:
        return self.bindings.list_for_entry(entry_id)

    def list_scope_entries(
        self,
        scope_ref: ScopeRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> list[ScopeEntryRecord]:
        scope_type, scope_value = scope_ref.as_tuple()
        return self.bindings.list_scope_entries(
            project_id,
            scope_type,
            scope_value,
            self.variants,
        )

    def count_scope(
        self,
        scope_ref: ScopeRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> int:
        scope_type, scope_value = scope_ref.as_tuple()
        return self.bindings.count_scope(
            project_id,
            scope_type,
            scope_value,
        )

    def clear_scope(
        self,
        scope_ref: ScopeRef,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> None:
        scope_type, scope_value = scope_ref.as_tuple()
        removed = self.bindings.clear_scope(project_id, scope_type, scope_value)
        for row in removed:
            self.lifecycle.refresh_orphan_states(int(row["entry_id"]))

    def remove_scope_bindings(
        self,
        scope_refs: list[ScopeRef],
        project_id: int = DEFAULT_PROJECT_ID,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        grouped_scope_values: dict[str, list[str]] = {}
        for scope_ref in scope_refs:
            scope_type, scope_value = scope_ref.as_tuple()
            grouped_scope_values.setdefault(scope_type, []).append(scope_value)
        removed: list[BindingRecord] = []
        for scope_type, scope_values in grouped_scope_values.items():
            removed.extend(self.bindings.remove_scope_bindings(project_id, scope_type, scope_values, conn=conn))
        for row in removed:
            self.lifecycle.refresh_orphan_states(int(row["entry_id"]), conn=conn)
        return len(removed)

    def remove_binding(
        self,
        entry_id: int,
        scope_ref: ScopeRef,
    ) -> BindingRecord | None:
        scope_type, scope_value = scope_ref.as_tuple()
        removed = self.bindings.delete(entry_id, scope_type, scope_value)
        if removed is None:
            return None
        self.lifecycle.refresh_orphan_states(int(removed["entry_id"]))
        return removed


class EntryVariantViewAssembler:
    def binding_summary(self, binding: BindingRecord) -> BindingSummary:
        return {
            "scope_ref": str(ScopeRef.parse(f"{binding['scope_type']}/{binding['scope_value']}")),
            "created_at": binding["created_at"],
            "updated_at": binding["updated_at"],
        }

    def assemble(self, item: ScopeEntryRecord, bindings: list[BindingRecord]) -> EntryVariantView:
        variant = item["variant"]
        return {
            "variant_id": int(variant["variant_id"]),
            "entry_id": int(item["entry_id"]),
            "project_id": int(item["project_id"]),
            "business_key": item["business_key"],
            "file_name": variant["file_name"],
            "source": variant["source"],
            "translations": variant["translations"],
            "remarks": variant["remarks"],
            "bindings": [self.binding_summary(binding) for binding in bindings],
            "trashed_at": variant["trashed_at"],
            "trash_until": variant["trash_until"],
            "restored_at": variant["restored_at"],
            "created_at": variant["created_at"],
            "updated_at": variant["updated_at"],
        }
