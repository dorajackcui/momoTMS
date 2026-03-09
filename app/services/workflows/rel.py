from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.io import normalize_non_content_value
from app.services.variant.services import EntryService, ScopeBindingService, VariantCatalogService


class RelService:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.entries = EntryService()
        self.bindings = ScopeBindingService()
        self.catalog = VariantCatalogService()

    def summary(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        members = self.bindings.list_scope_entries("rel", "current", project_id)
        return {
            "count": len(members),
            "business_keys": [item["business_key"] for item in members[:20]],
        }

    def active_hotfix(
        self,
        business_key: str,
        lang: str,
        target_text: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_language(lang, project_id)
        rel_item = self._require_rel_variant(business_key, project_id)
        translations = dict(rel_item["variant"]["translations"])
        translations[lang] = target_text
        self.catalog.replace_translations(int(rel_item["variant"]["variant_id"]), translations)
        summary = {
            "business_key": business_key,
            "lang": lang,
            "status": "UPDATED_TARGET",
        }
        return {
            "summary": summary,
            "report_rows": [
                {
                    "business_key": business_key,
                    "lang": lang,
                    "status": "UPDATED_TARGET",
                }
            ],
        }

    def passive_hotfix(
        self,
        business_key: str,
        source: str,
        translations_by_lang: dict[str, str],
        remarks_by_key: dict[str, str],
        file_name: str | None = None,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        rel_item = self._require_rel_variant(business_key, project_id)
        variant = rel_item["variant"]
        merged_translations = dict(variant["translations"])
        merged_translations.update(translations_by_lang)
        merged_remarks = dict(variant["remarks"])
        merged_remarks.update(remarks_by_key)
        target_file_name = file_name if file_name is not None else variant["file_name"]
        normalized_source = normalize_non_content_value(source)

        if normalized_source == variant["source"]:
            self.catalog.update_variant(
                variant_id=int(variant["variant_id"]),
                file_name=target_file_name,
                source=normalized_source,
                translations=merged_translations,
                remarks=merged_remarks,
            )
            status = "UPDATED_CANONICAL"
        else:
            entry_id = int(rel_item["entry"]["entry_id"])
            target_variant = self.catalog.find_variant_by_source(
                entry_id,
                normalized_source,
                include_trashed=False,
            )
            if target_variant is None:
                target_variant_id = self.catalog.create_variant(
                    entry_id,
                    file_name=target_file_name,
                    source=normalized_source,
                    translations=merged_translations,
                    remarks=merged_remarks,
                )
                status = "CREATED_SOURCE_VARIANT"
            else:
                target_variant_id = int(target_variant["variant_id"])
                self.catalog.update_variant(
                    variant_id=target_variant_id,
                    file_name=target_file_name,
                    source=normalized_source,
                    translations=merged_translations,
                    remarks=merged_remarks,
                )
                status = "REBOUND_SOURCE_VARIANT"
            self.bindings.bind_scope(entry_id, "rel", "current", target_variant_id)
        summary = {
            "business_key": business_key,
            "updated_languages": sorted(translations_by_lang),
            "updated_remarks": sorted(remarks_by_key),
            "status": status,
        }
        return {
            "summary": summary,
            "report_rows": [
                {
                    "business_key": business_key,
                    "status": status,
                }
            ],
        }

    def _require_rel_variant(self, business_key: str, project_id: int) -> dict[str, Any]:
        entry = self.entries.get_entry(business_key, project_id=project_id)
        if entry is None:
            raise KeyError(f"business_key not found in current rel: {business_key}")
        binding = self.bindings.get_binding(int(entry["entry_id"]), "rel", "current")
        if binding is None:
            raise KeyError(f"business_key not found in current rel: {business_key}")
        return {
            "entry": entry,
            "binding": binding,
            "variant": self.catalog.get_variant(int(binding["variant_id"])),
        }
