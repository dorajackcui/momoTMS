from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.variant.facade import VariantService


class StringService:
    def __init__(self) -> None:
        self.variants = VariantService()

    def list_strings(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        search: str | None = None,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        items = self.variants.list_preferred_entry_views(project_id=project_id, search=search)
        if include_deleted:
            return items
        return [item for item in items if item["deleted_at"] is None]

    def get_string(
        self,
        business_key: str,
        project_id: int = DEFAULT_PROJECT_ID,
        include_deleted: bool = True,
    ) -> dict[str, Any] | None:
        item = self.variants.get_preferred_entry_view(business_key, project_id=project_id)
        if item is None:
            return None
        if not include_deleted and item["deleted_at"] is not None:
            return None
        return item

    def create_string(
        self,
        business_key: str,
        file_name: str | None,
        source: str,
        translations: dict[str, str | None],
        remarks: dict[str, str | None],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> int:
        entry = self.variants.get_or_create_entry(business_key, project_id=project_id)
        reusable = self.variants.find_reusable_variant(
            int(entry["entry_id"]),
            file_name=file_name,
            source=source,
            translations=translations,
            remarks=remarks,
        )
        if reusable:
            self.variants.update_variant(
                variant_id=int(reusable["variant_id"]),
                file_name=file_name,
                source=source,
                translations=translations,
                remarks=remarks,
            )
            return int(reusable["variant_id"])
        return self.variants.create_variant(
            int(entry["entry_id"]),
            file_name=file_name,
            source=source,
            translations=translations,
            remarks=remarks,
        )

    def update_canonical(
        self,
        string_id: int,
        file_name: str | None,
        source: str,
        translations: dict[str, str | None],
        remarks: dict[str, str | None],
        restore_if_deleted: bool = False,
    ) -> None:
        self.variants.update_variant(
            variant_id=string_id,
            file_name=file_name,
            source=source,
            translations=translations,
            remarks=remarks,
            restore_if_trashed=restore_if_deleted,
        )

    def replace_translations(self, string_id: int, translations: dict[str, str | None]) -> None:
        self.variants.replace_translations(string_id, translations)

    def replace_remarks(self, string_id: int, remarks: dict[str, str | None]) -> None:
        self.variants.replace_remarks(string_id, remarks)

    def ensure_membership(self, string_id: int, membership_type: str, membership_value: str) -> None:
        variant = self.variants.get_variant(string_id)
        self.variants.bind_scope(
            entry_id=int(variant["entry_id"]),
            scope_type=membership_type,
            scope_value=membership_value,
            variant_id=string_id,
        )

    def has_membership(self, string_id: int, membership_type: str, membership_value: str) -> bool:
        variant = self.variants.get_variant(string_id)
        binding = self.variants.get_binding(
            int(variant["entry_id"]),
            membership_type,
            membership_value,
        )
        return binding is not None and int(binding["variant_id"]) == int(string_id)

    def get_membership_strings(
        self,
        membership_type: str,
        membership_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> list[dict[str, Any]]:
        results = self.variants.list_scope_entries(membership_type, membership_value, project_id)
        return [
            {
                "string_id": int(item["variant"]["variant_id"]),
                "entry_id": int(item["entry_id"]),
                "project_id": int(item["project_id"]),
                "business_key": item["business_key"],
                "file_name": item["variant"]["file_name"],
                "source": item["variant"]["source"],
                "translations": item["variant"]["translations"],
                "remarks": item["variant"]["remarks"],
                "memberships": [
                    {
                        "membership_type": binding["scope_type"],
                        "membership_value": binding["scope_value"],
                    }
                    for binding in self.variants.list_bindings_for_entry(int(item["entry_id"]))
                ],
                "deleted_at": item["variant"]["trashed_at"],
                "trash_until": item["variant"]["trash_until"],
                "restored_at": item["variant"]["restored_at"],
                "created_at": item["variant"]["created_at"],
                "updated_at": item["variant"]["updated_at"],
            }
            for item in results
        ]

    def membership_count(
        self,
        membership_type: str,
        membership_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> int:
        return self.variants.count_scope(membership_type, membership_value, project_id)

    def clear_rel_memberships(self, project_id: int = DEFAULT_PROJECT_ID) -> None:
        self.variants.clear_scope("rel", "current", project_id)

    def remove_dev_memberships(
        self,
        versions: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> int:
        return self.variants.remove_scope_bindings("dev", versions, project_id)

    def soft_delete(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
        trash_days: int = 30,
    ) -> dict[str, list[str]]:
        return self.variants.trash_entries(business_keys, project_id, trash_days)

    def restore(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, list[str]]:
        return self.variants.restore_entries(business_keys, project_id)

    def trash_count(self, project_id: int = DEFAULT_PROJECT_ID) -> int:
        return self.variants.trash_count(project_id)
