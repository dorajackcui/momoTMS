from __future__ import annotations

from typing import Any

from app.services.workflows.dev_versions import DevVersionService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.variant.services import EntryService, ScopeBindingService, VariantCatalogService


class ReadModelService:
    def __init__(self) -> None:
        self.dev_versions = DevVersionService()
        self.entries = EntryService()
        self.bindings = ScopeBindingService()
        self.catalog = VariantCatalogService()

    def scope_summary(self, project_id: int = DEFAULT_PROJECT_ID, lang: str | None = None) -> dict[str, Any]:
        rel_entries = self.bindings.list_scope_entries("rel", "current", project_id)
        rel_key_map = {item["business_key"]: item for item in rel_entries}
        scopes = [
            {
                "scope_type": "rel",
                "scope_value": "current",
                "entry_count": len(rel_entries),
                "status_counts": {
                    "aligned": len(rel_entries),
                    "diverged": 0,
                    "base_only": 0,
                    "target_only": 0,
                },
            }
        ]
        for version in self.dev_versions.list_versions(project_id=project_id, active_only=True):
            members = self.bindings.list_scope_entries("dev", version["version"], project_id)
            compare = self._compare_maps(rel_key_map, {item["business_key"]: item for item in members}, lang)
            scopes.append(
                {
                    "scope_type": "dev",
                    "scope_value": version["version"],
                    "entry_count": len(members),
                    "status_counts": compare["status_counts"],
                    "version_line": version["version_line"],
                    "is_candidate_release": version["is_candidate_release"],
                }
            )
        return {"scopes": scopes}

    def compare_scopes(
        self,
        base_scope_type: str,
        base_scope_value: str,
        target_scope_type: str,
        target_scope_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
        lang: str | None = None,
        search: str | None = None,
        states: list[str] | None = None,
        diff_categories: list[str] | None = None,
        priority_statuses: list[str] | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        base_entries = self.bindings.list_scope_entries(base_scope_type, base_scope_value, project_id)
        target_entries = self.bindings.list_scope_entries(target_scope_type, target_scope_value, project_id)
        base_map = {item["business_key"]: item for item in base_entries}
        target_map = {item["business_key"]: item for item in target_entries}
        compare = self._compare_maps(
            base_map,
            target_map,
            lang,
            search=search,
            states=states,
            diff_categories=diff_categories,
            priority_statuses=priority_statuses,
            page=page,
            page_size=page_size,
        )
        compare["base_scope"] = f"{base_scope_type}/{base_scope_value}"
        compare["target_scope"] = f"{target_scope_type}/{target_scope_value}"
        return compare

    def translation_queue(
        self,
        target_scope_type: str,
        target_scope_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
        lang: str | None = None,
        search: str | None = None,
        priority_statuses: list[str] | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        compare = self.compare_scopes(
            "rel",
            "current",
            target_scope_type,
            target_scope_value,
            project_id=project_id,
            lang=lang,
            search=search,
            priority_statuses=priority_statuses,
            page=page,
            page_size=page_size,
        )
        counts: dict[str, int] = {}
        for row in compare["priority_rows_full"]:
            status = row["priority_status"]
            counts[status] = counts.get(status, 0) + 1
        return {
            "target_scope": f"{target_scope_type}/{target_scope_value}",
            "lang": lang,
            "status_counts": counts,
            "rows": compare["priority_rows"],
            "total_rows": compare["total_priority_rows"],
            "page": compare["page"],
            "page_size": compare["page_size"],
        }

    def master_entry(self, business_key: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        entry = self.entries.get_entry(business_key, project_id)
        if not entry:
            raise KeyError(f"entry not found: {business_key}")
        bindings = self.bindings.list_bindings_for_entry(int(entry["entry_id"]))
        active_results = []
        for binding in bindings:
            variant = self.catalog.get_variant(int(binding["variant_id"]))
            if variant["trashed_at"] is not None:
                continue
            active_results.append(
                {
                    "business_key": entry["business_key"],
                    "scope_type": binding["scope_type"],
                    "scope_value": binding["scope_value"],
                    "variant_id": int(variant["variant_id"]),
                    "file_name": variant["file_name"],
                    "source": variant["source"],
                    "translations": variant["translations"],
                    "remarks": variant["remarks"],
                }
            )
        return {
            "business_key": entry["business_key"],
            "entry_id": int(entry["entry_id"]),
            "results": active_results,
        }

    def master_search(self, source: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        needle = source
        results: list[dict[str, Any]] = []
        rel_entries = self.bindings.list_scope_entries("rel", "current", project_id)
        for item in rel_entries:
            variant = item["variant"]
            if variant["source"] == needle:
                results.append(self._search_row(item))
        for version in self.dev_versions.list_versions(project_id=project_id, active_only=True):
            for item in self.bindings.list_scope_entries("dev", version["version"], project_id):
                variant = item["variant"]
                if variant["source"] == needle:
                    results.append(self._search_row(item))
        return {"source": needle, "results": results}

    def _search_row(self, item: dict[str, Any]) -> dict[str, Any]:
        variant = item["variant"]
        return {
            "business_key": item["business_key"],
            "scope_type": item["scope_type"],
            "scope_value": item["scope_value"],
            "variant_id": int(variant["variant_id"]),
            "file_name": variant["file_name"],
            "source": variant["source"],
            "translations": variant["translations"],
            "remarks": variant["remarks"],
        }

    def _compare_maps(
        self,
        base_map: dict[str, dict[str, Any]],
        target_map: dict[str, dict[str, Any]],
        lang: str | None,
        search: str | None = None,
        states: list[str] | None = None,
        diff_categories: list[str] | None = None,
        priority_statuses: list[str] | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        all_rows: list[dict[str, Any]] = []
        status_counts = {"aligned": 0, "diverged": 0, "base_only": 0, "target_only": 0}
        for business_key in sorted(set(base_map) | set(target_map)):
            base_item = base_map.get(business_key)
            target_item = target_map.get(business_key)
            state, row_diff_categories = self._branch_state(base_item, target_item)
            priority_status = self._priority_status(base_item, target_item, state, row_diff_categories, lang)
            status_counts[state] = status_counts.get(state, 0) + 1
            all_rows.append(
                {
                    "business_key": business_key,
                    "state": state,
                    "diff_categories": row_diff_categories,
                    "priority_status": priority_status,
                    "base": self._compare_side(base_item),
                    "target": self._compare_side(target_item),
                }
            )
        full_priority_rows = [
            {
                "business_key": row["business_key"],
                "priority_status": row["priority_status"],
                "state": row["state"],
                "diff_categories": row["diff_categories"],
                "file_name": self._preferred_file_name(row["target"], row["base"]),
                "source": self._preferred_source(row["target"], row["base"]),
                "target_text": self._preferred_target_text(row["target"], row["base"], lang),
            }
            for row in all_rows
        ]
        filtered_rows = self._filter_compare_rows(
            all_rows,
            search=search,
            states=states,
            diff_filter=diff_categories,
            priority_statuses=priority_statuses,
        )
        filtered_priority_rows = self._build_priority_rows(filtered_rows, lang)
        page_value, page_size_value, paged_rows = self._paginate(filtered_rows, page, page_size)
        _, _, paged_priority_rows = self._paginate(filtered_priority_rows, page, page_size)
        return {
            "status_counts": status_counts,
            "rows": paged_rows,
            "priority_rows": paged_priority_rows,
            "priority_rows_full": full_priority_rows,
            "total_rows": len(filtered_rows),
            "total_priority_rows": len(filtered_priority_rows),
            "page": page_value,
            "page_size": page_size_value,
        }

    def _filter_compare_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        search: str | None,
        states: list[str] | None,
        diff_filter: list[str] | None,
        priority_statuses: list[str] | None,
    ) -> list[dict[str, Any]]:
        search_value = (search or "").strip().lower()
        state_set = set(states or [])
        diff_set = set(diff_filter or [])
        priority_set = set(priority_statuses or [])
        filtered: list[dict[str, Any]] = []
        for row in rows:
            if search_value and search_value not in row["business_key"].lower():
                continue
            if state_set and row["state"] not in state_set:
                continue
            if diff_set and not diff_set.intersection(set(row["diff_categories"])):
                continue
            if priority_set and row["priority_status"] not in priority_set:
                continue
            filtered.append(row)
        return filtered

    def _build_priority_rows(self, rows: list[dict[str, Any]], lang: str | None) -> list[dict[str, Any]]:
        return [
            {
                "business_key": row["business_key"],
                "priority_status": row["priority_status"],
                "state": row["state"],
                "diff_categories": row["diff_categories"],
                "file_name": self._preferred_file_name(row["target"], row["base"]),
                "source": self._preferred_source(row["target"], row["base"]),
                "target_text": self._preferred_target_text(row["target"], row["base"], lang),
            }
            for row in rows
        ]

    def _paginate(
        self,
        rows: list[dict[str, Any]],
        page: int,
        page_size: int | None,
    ) -> tuple[int, int, list[dict[str, Any]]]:
        if page_size is None or page_size <= 0:
            return 1, len(rows), rows
        page_value = max(page, 1)
        start = (page_value - 1) * page_size
        end = start + page_size
        return page_value, page_size, rows[start:end]

    def _preferred_file_name(self, target: dict[str, Any] | None, base: dict[str, Any] | None) -> str | None:
        preferred = target or base
        if preferred is None:
            return None
        return preferred["file_name"]

    def _preferred_source(self, target: dict[str, Any] | None, base: dict[str, Any] | None) -> str:
        preferred = target or base
        if preferred is None:
            return ""
        return preferred["source"]

    def _preferred_target_text(
        self,
        target: dict[str, Any] | None,
        base: dict[str, Any] | None,
        lang: str | None,
    ) -> str:
        if lang is None:
            return ""
        preferred = target or base
        if preferred is None:
            return ""
        return preferred["translations"].get(lang, "")

    def _compare_side(self, item: dict[str, Any] | None) -> dict[str, Any] | None:
        if item is None:
            return None
        variant = item["variant"]
        return {
            "scope_type": item["scope_type"],
            "scope_value": item["scope_value"],
            "variant_id": int(variant["variant_id"]),
            "file_name": variant["file_name"],
            "source": variant["source"],
            "translations": variant["translations"],
            "remarks": variant["remarks"],
        }

    def _branch_state(
        self,
        base_item: dict[str, Any] | None,
        target_item: dict[str, Any] | None,
    ) -> tuple[str, list[str]]:
        if base_item and not target_item:
            return "base_only", []
        if target_item and not base_item:
            return "target_only", []
        if not base_item and not target_item:
            return "target_only", []
        base_variant = base_item["variant"]
        target_variant = target_item["variant"]
        diff_categories: list[str] = []
        if base_variant["source"] != target_variant["source"]:
            diff_categories.append("source_changed")
        if dict(base_variant["translations"]) != dict(target_variant["translations"]):
            diff_categories.append("translation_changed")
        if dict(base_variant["remarks"]) != dict(target_variant["remarks"]):
            diff_categories.append("remark_changed")
        if base_variant["file_name"] != target_variant["file_name"]:
            diff_categories.append("file_name_changed")
        if diff_categories:
            return "diverged", diff_categories
        return "aligned", diff_categories

    def _priority_status(
        self,
        base_item: dict[str, Any] | None,
        target_item: dict[str, Any] | None,
        state: str,
        diff_categories: list[str],
        lang: str | None,
    ) -> str:
        if lang is None:
            return "needs_review" if state == "diverged" else "already_translated"
        base_target = self._lang_value(base_item, lang)
        target_target = self._lang_value(target_item, lang)
        if state == "diverged" and "source_changed" in diff_categories:
            return "source_mismatch"
        if state == "rel_only":
            return "fillable" if base_target else "needs_translation"
        if state == "dev_only":
            return "already_translated" if target_target else "needs_translation"
        if state == "aligned":
            return "already_translated" if target_target else "needs_translation"
        if not target_target and base_target:
            return "fillable"
        if not target_target:
            return "needs_translation"
        if diff_categories:
            return "needs_review"
        return "already_translated"

    def _lang_value(self, item: dict[str, Any] | None, lang: str) -> str:
        if item is None:
            return ""
        return item["variant"]["translations"].get(lang, "")
