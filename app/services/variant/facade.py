from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.variant.services import (
    EntryService,
    PreferredEntryViewService,
    ScopeBindingService,
    VariantCatalogService,
    VariantLifecycleService,
)
from app.services.variant.repositories import (
    EntryRepository,
    RetainedVariantRepository,
    ScopeBindingRepository,
    VariantRepository,
)


class VariantService:
    """Compatibility facade over the split entry/variant/binding services."""

    def __init__(self) -> None:
        entry_repo = EntryRepository()
        variant_repo = VariantRepository()
        binding_repo = ScopeBindingRepository()
        retained_repo = RetainedVariantRepository()

        self.entries = EntryService(entry_repo)
        self.catalog = VariantCatalogService(variant_repo)
        self.lifecycle = VariantLifecycleService(variant_repo, binding_repo, retained_repo)
        self.bindings = ScopeBindingService(variant_repo, binding_repo, retained_repo, self.lifecycle)
        self.views = PreferredEntryViewService(self.entries, self.catalog, self.bindings, self.lifecycle)

    def get_or_create_entry(
        self,
        business_key: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self.entries.get_or_create_entry(business_key, project_id)

    def get_entry(
        self,
        business_key: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any] | None:
        return self.entries.get_entry(business_key, project_id)

    def ensure_entries(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, dict[str, Any]]:
        return self.entries.ensure_entries(business_keys, project_id)

    def get_entries_by_keys(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, dict[str, Any]]:
        return self.entries.get_entries_by_keys(business_keys, project_id)

    def list_entries(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.entries.list_entries(project_id, search)

    def create_variant(
        self,
        entry_id: int,
        file_name: str | None,
        source: str,
        translations: dict[str, str | None],
        remarks: dict[str, str | None],
    ) -> int:
        return self.catalog.create_variant(entry_id, file_name, source, translations, remarks)

    def update_variant(
        self,
        variant_id: int,
        file_name: str | None,
        source: str,
        translations: dict[str, str | None],
        remarks: dict[str, str | None],
        restore_if_trashed: bool = False,
    ) -> None:
        self.catalog.update_variant(
            variant_id,
            file_name,
            source,
            translations,
            remarks,
            restore_if_trashed=restore_if_trashed,
        )

    def replace_translations(self, variant_id: int, translations: dict[str, str | None]) -> None:
        self.catalog.replace_translations(variant_id, translations)

    def replace_remarks(self, variant_id: int, remarks: dict[str, str | None]) -> None:
        self.catalog.replace_remarks(variant_id, remarks)

    def get_variant(self, variant_id: int) -> dict[str, Any]:
        return self.catalog.get_variant(variant_id)

    def find_reusable_variant(
        self,
        entry_id: int,
        file_name: str | None,
        source: str,
        translations: dict[str, str | None],
        remarks: dict[str, str | None],
    ) -> dict[str, Any] | None:
        return self.catalog.find_reusable_variant(entry_id, file_name, source, translations, remarks)

    def list_variants(
        self,
        entry_id: int,
        include_trashed: bool = True,
    ) -> list[dict[str, Any]]:
        return self.catalog.list_variants(entry_id, include_trashed)

    def list_variants_for_entries(
        self,
        entry_ids: list[int],
        include_trashed: bool = True,
    ) -> dict[int, list[dict[str, Any]]]:
        return self.catalog.list_variants_for_entries(entry_ids, include_trashed)

    def bind_scope(
        self,
        entry_id: int,
        scope_type: str,
        scope_value: str,
        variant_id: int,
    ) -> None:
        self.bindings.bind_scope(entry_id, scope_type, scope_value, variant_id)

    def get_binding(
        self,
        entry_id: int,
        scope_type: str,
        scope_value: str,
    ) -> dict[str, Any] | None:
        return self.bindings.get_binding(entry_id, scope_type, scope_value)

    def get_bindings_for_entries(
        self,
        entry_ids: list[int],
        scope_type: str,
        scope_value: str,
    ) -> dict[int, dict[str, Any]]:
        return self.bindings.get_bindings_for_entries(entry_ids, scope_type, scope_value)

    def list_bindings_for_entry(self, entry_id: int) -> list[dict[str, Any]]:
        return self.bindings.list_bindings_for_entry(entry_id)

    def list_retained_for_entry(self, entry_id: int) -> list[dict[str, Any]]:
        return self.lifecycle.list_retained_for_entry(entry_id)

    def list_scope_entries(
        self,
        scope_type: str,
        scope_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> list[dict[str, Any]]:
        return self.bindings.list_scope_entries(scope_type, scope_value, project_id)

    def count_scope(
        self,
        scope_type: str,
        scope_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> int:
        return self.bindings.count_scope(scope_type, scope_value, project_id)

    def clear_scope(
        self,
        scope_type: str,
        scope_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> None:
        self.bindings.clear_scope(scope_type, scope_value, project_id)

    def remove_scope_bindings(
        self,
        scope_type: str,
        scope_values: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> int:
        return self.bindings.remove_scope_bindings(scope_type, scope_values, project_id)

    def trash_entries(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
        trash_days: int = 30,
    ) -> dict[str, list[str]]:
        return self.lifecycle.trash_entries(business_keys, project_id, trash_days)

    def restore_entries(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, list[str]]:
        return self.lifecycle.restore_entries(business_keys, project_id)

    def trash_count(self, project_id: int = DEFAULT_PROJECT_ID) -> int:
        return self.lifecycle.trash_count(project_id)

    def get_preferred_entry_view(
        self,
        business_key: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any] | None:
        return self.views.get_preferred_entry_view(business_key, project_id)

    def list_preferred_entry_views(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.views.list_preferred_entry_views(project_id, search)

    def _compat_entry_view(self, entry: dict[str, Any]) -> dict[str, Any]:
        return self.views.compat_entry_view(entry)

    def _preferred_variant_for_entry(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        return self.views.preferred_variant_for_entry(entry)

    def _refresh_orphan_states(self, entry_id: int) -> None:
        self.lifecycle.refresh_orphan_states(entry_id)

    def _retain_variant_if_inactive(
        self,
        variant_id: int,
        entry_id: int,
        last_active_scope_type: str,
        last_active_scope_value: str,
    ) -> None:
        self.lifecycle.retain_variant_if_inactive(
            variant_id,
            entry_id,
            last_active_scope_type,
            last_active_scope_value,
        )

    def _is_retained_variant(self, variant_id: int) -> bool:
        return self.lifecycle.is_retained_variant(variant_id)

    def list_retained_entries(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> list[dict[str, Any]]:
        return self.lifecycle.list_retained_entries(project_id)
