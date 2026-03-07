from __future__ import annotations

from typing import Any

from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.variant.compatibility import StringService


class RelService:
    def __init__(self) -> None:
        self.strings = StringService()

    def summary(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        members = self.strings.get_membership_strings("rel", "current", project_id)
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
        string_item = self._require_rel_string(business_key, project_id)
        translations = dict(string_item["translations"])
        translations[lang] = target_text
        self.strings.replace_translations(int(string_item["string_id"]), translations)
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
        string_item = self._require_rel_string(business_key, project_id)
        merged_translations = dict(string_item["translations"])
        merged_translations.update(translations_by_lang)
        merged_remarks = dict(string_item["remarks"])
        merged_remarks.update(remarks_by_key)
        self.strings.update_canonical(
            string_id=int(string_item["string_id"]),
            file_name=file_name if file_name is not None else string_item["file_name"],
            source=source,
            translations=merged_translations,
            remarks=merged_remarks,
        )
        summary = {
            "business_key": business_key,
            "updated_languages": sorted(translations_by_lang),
            "updated_remarks": sorted(remarks_by_key),
            "status": "UPDATED_CANONICAL",
        }
        return {
            "summary": summary,
            "report_rows": [
                {
                    "business_key": business_key,
                    "status": "UPDATED_CANONICAL",
                }
            ],
        }

    def _require_rel_string(self, business_key: str, project_id: int) -> dict[str, Any]:
        string_item = self.strings.get_string(
            business_key,
            project_id=project_id,
            include_deleted=False,
        )
        if not string_item or not self.strings.has_membership(int(string_item["string_id"]), "rel", "current"):
            raise KeyError(f"business_key not found in current rel: {business_key}")
        return string_item
