from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.shared.io import (
    normalize_content_map,
    normalize_non_content_map,
    normalize_non_content_value,
)
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.utils import now_iso
from app.services.variant.records import (
    BindingRecord,
    EntryRecord,
    PreferredEntryView,
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
        for variant in self.list_variants(entry_id, include_trashed=False):
            if variant["source"] == normalized_source:
                return variant
        return None

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


class CanonicalVariantService:
    def __init__(
        self,
        variants: VariantCatalogService | None = None,
        bindings: ScopeBindingRepository | None = None,
    ) -> None:
        self.variants = variants or VariantCatalogService()
        self.bindings = bindings or ScopeBindingRepository()

    def list_canonical_variants(
        self,
        entry_id: int,
        include_trashed: bool = True,
    ) -> list[VariantRecord]:
        variants = self.variants.list_variants(entry_id, include_trashed=include_trashed)
        if not variants:
            return []
        bindings_by_variant = self._bindings_by_variant(entry_id)
        variants_by_source: dict[str, list[VariantRecord]] = defaultdict(list)
        for variant in variants:
            variants_by_source[variant["source"]].append(variant)
        canonical_variants = [
            self._choose_canonical_variant(group, bindings_by_variant)
            for group in variants_by_source.values()
        ]
        return sorted(canonical_variants, key=lambda item: int(item["variant_id"]))

    def find_canonical_variant_by_source(
        self,
        entry_id: int,
        source: str,
        include_trashed: bool = False,
    ) -> VariantRecord | None:
        normalized_source = normalize_non_content_value(source)
        if not normalized_source:
            raise ValueError("source is required")
        variants = [
            item
            for item in self.list_canonical_variants(entry_id, include_trashed=include_trashed)
            if item["source"] == normalized_source
        ]
        if not variants:
            return None
        return variants[0]

    def is_rel_bound(self, entry_id: int, variant_id: int) -> bool:
        return any(
            binding["scope_type"] == "rel" and binding["scope_value"] == "current"
            for binding in self._bindings_by_variant(entry_id).get(variant_id, [])
        )

    def binding_count(self, entry_id: int, variant_id: int) -> int:
        return len(self._bindings_by_variant(entry_id).get(variant_id, []))

    def _bindings_by_variant(self, entry_id: int) -> dict[int, list[BindingRecord]]:
        grouped: dict[int, list[BindingRecord]] = defaultdict(list)
        for binding in self.bindings.list_for_entry(entry_id):
            grouped[int(binding["variant_id"])].append(binding)
        return grouped

    def _choose_canonical_variant(
        self,
        variants: list[VariantRecord],
        bindings_by_variant: dict[int, list[BindingRecord]],
    ) -> VariantRecord:
        return max(
            variants,
            key=lambda item: self._variant_rank(item, bindings_by_variant),
        )

    def _variant_rank(
        self,
        variant: VariantRecord,
        bindings_by_variant: dict[int, list[BindingRecord]],
    ) -> tuple[int, int, int, int, str, int]:
        variant_id = int(variant["variant_id"])
        bindings = bindings_by_variant.get(variant_id, [])
        rel_bound = any(
            binding["scope_type"] == "rel" and binding["scope_value"] == "current"
            for binding in bindings
        )
        active = bool(bindings)
        non_trashed = variant["trashed_at"] is None
        orphan_like = non_trashed and not active and variant["orphaned_at"] is not None
        return (
            1 if non_trashed else 0,
            1 if rel_bound else 0,
            1 if active else 0,
            1 if orphan_like else 0,
            variant["updated_at"],
            variant_id,
        )


class VariantLifecycleService:
    def __init__(
        self,
        variants: VariantRepository | None = None,
        bindings: ScopeBindingRepository | None = None,
    ) -> None:
        self.variants = variants or VariantRepository()
        self.bindings = bindings or ScopeBindingRepository()

    def refresh_orphan_states(self, entry_id: int) -> None:
        variant_rows = self.variants.list_by_entry(entry_id, include_trashed=True)
        binding_counts = self.bindings.binding_counts_for_entry(entry_id)
        timestamp = now_iso()
        for variant in variant_rows:
            variant_id = int(variant["variant_id"])
            if variant["trashed_at"] is not None:
                orphaned_at = None
            elif binding_counts.get(variant_id, 0) == 0:
                orphaned_at = variant["orphaned_at"] or timestamp
            else:
                orphaned_at = None
            self.variants.set_orphaned_at(variant_id, orphaned_at)

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

    def restore_variant(self, variant_id: int, entry_id: int) -> None:
        self.variants.restore_variant(variant_id, now_iso())
        self.refresh_orphan_states(entry_id)

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
        scope_type: str,
        scope_value: str,
        variant_id: int,
    ) -> None:
        normalized_scope_value = self._require_non_content("scope_value", scope_value)
        timestamp = now_iso()
        self.bindings.upsert(
            entry_id,
            scope_type,
            normalized_scope_value,
            variant_id,
            timestamp,
        )
        self.variants.clear_orphaned_at(variant_id, timestamp)
        self.lifecycle.refresh_orphan_states(entry_id)

    def get_binding(self, entry_id: int, scope_type: str, scope_value: str) -> BindingRecord | None:
        return self.bindings.get(entry_id, scope_type, self._require_non_content("scope_value", scope_value))

    def get_bindings_for_entries(
        self,
        entry_ids: list[int],
        scope_type: str,
        scope_value: str,
    ) -> dict[int, BindingRecord]:
        return self.bindings.get_for_entries(
            entry_ids,
            scope_type,
            self._require_non_content("scope_value", scope_value),
        )

    def list_bindings_for_entry(self, entry_id: int) -> list[BindingRecord]:
        return self.bindings.list_for_entry(entry_id)

    def list_scope_entries(
        self,
        scope_type: str,
        scope_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> list[ScopeEntryRecord]:
        return self.bindings.list_scope_entries(
            project_id,
            scope_type,
            self._require_non_content("scope_value", scope_value),
            self.variants,
        )

    def count_scope(
        self,
        scope_type: str,
        scope_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> int:
        return self.bindings.count_scope(
            project_id,
            scope_type,
            self._require_non_content("scope_value", scope_value),
        )

    def clear_scope(
        self,
        scope_type: str,
        scope_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> None:
        normalized_scope_value = self._require_non_content("scope_value", scope_value)
        removed = self.bindings.clear_scope(project_id, scope_type, normalized_scope_value)
        for row in removed:
            self.lifecycle.refresh_orphan_states(int(row["entry_id"]))

    def remove_scope_bindings(
        self,
        scope_type: str,
        scope_values: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> int:
        normalized_scope_values = [self._require_non_content("scope_value", value) for value in scope_values]
        removed = self.bindings.remove_scope_bindings(project_id, scope_type, normalized_scope_values)
        for row in removed:
            self.lifecycle.refresh_orphan_states(int(row["entry_id"]))
        return len(removed)

    def remove_binding(
        self,
        entry_id: int,
        scope_type: str,
        scope_value: str,
    ) -> BindingRecord | None:
        normalized_scope_value = self._require_non_content("scope_value", scope_value)
        removed = self.bindings.delete(entry_id, scope_type, normalized_scope_value)
        if removed is None:
            return None
        self.lifecycle.refresh_orphan_states(int(removed["entry_id"]))
        return removed

    def _require_non_content(self, field_name: str, value: Any) -> str:
        normalized = normalize_non_content_value(value)
        if not normalized:
            raise ValueError(f"{field_name} is required")
        return normalized


class PreferredEntryViewService:
    def __init__(
        self,
        entries: EntryService | None = None,
        variants: VariantCatalogService | None = None,
        bindings: ScopeBindingService | None = None,
        lifecycle: VariantLifecycleService | None = None,
    ) -> None:
        self.entries = entries or EntryService()
        self.variants = variants or VariantCatalogService()
        self.bindings = bindings or ScopeBindingService()
        self.lifecycle = lifecycle or VariantLifecycleService()
        self.canonical = CanonicalVariantService(self.variants, self.bindings.bindings)

    def get_preferred_entry_view(
        self,
        business_key: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> PreferredEntryView | None:
        entry = self.entries.get_entry(business_key, project_id)
        if entry is None:
            return None
        return self.compat_entry_view(entry)

    def list_preferred_entry_views(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        search: str | None = None,
    ) -> list[PreferredEntryView]:
        return [self.compat_entry_view(entry) for entry in self.entries.list_entries(project_id, search)]

    def compat_entry_view(self, entry: EntryRecord) -> PreferredEntryView:
        preferred_variant = self.preferred_variant_for_entry(entry)
        bindings = self.bindings.list_bindings_for_entry(int(entry["entry_id"]))
        memberships = [
            {
                "membership_type": binding["scope_type"],
                "membership_value": binding["scope_value"],
            }
            for binding in bindings
        ]
        if preferred_variant is None:
            return {
                "string_id": 0,
                "entry_id": int(entry["entry_id"]),
                "project_id": int(entry["project_id"]),
                "business_key": entry["business_key"],
                "file_name": "",
                "source": "",
                "translations": {},
                "remarks": {},
                "memberships": memberships,
                "deleted_at": None,
                "trash_until": None,
                "restored_at": None,
                "created_at": entry["created_at"],
                "updated_at": entry["updated_at"],
            }
        return {
            "string_id": int(preferred_variant["variant_id"]),
            "entry_id": int(entry["entry_id"]),
            "project_id": int(entry["project_id"]),
            "business_key": entry["business_key"],
            "file_name": preferred_variant["file_name"],
            "source": preferred_variant["source"],
            "translations": preferred_variant["translations"],
            "remarks": preferred_variant["remarks"],
            "memberships": memberships,
            "deleted_at": preferred_variant["trashed_at"],
            "trash_until": preferred_variant["trash_until"],
            "restored_at": preferred_variant["restored_at"],
            "created_at": preferred_variant["created_at"],
            "updated_at": preferred_variant["updated_at"],
        }

    def preferred_variant_for_entry(self, entry: EntryRecord) -> VariantRecord | None:
        bindings = self.bindings.list_bindings_for_entry(int(entry["entry_id"]))
        preferred_binding = None
        for binding in bindings:
            if binding["scope_type"] == "rel" and binding["scope_value"] == "current":
                preferred_binding = binding
                break
        if preferred_binding is None and bindings:
            preferred_binding = sorted(
                bindings,
                key=lambda item: (item["scope_type"] != "dev", item["scope_value"]),
            )[0]
        if preferred_binding is not None:
            return self.variants.get_variant(int(preferred_binding["variant_id"]))
        variants = self.canonical.list_canonical_variants(int(entry["entry_id"]), include_trashed=True)
        non_trashed = [variant for variant in variants if variant["trashed_at"] is None]
        if non_trashed:
            return non_trashed[-1]
        if variants:
            return variants[-1]
        return None
