from __future__ import annotations

from typing import Any

from app.db import get_conn
from app.services.branch.models import BranchRef
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.variant.services import EntryService, ScopeBindingService, VariantCatalogService


class ReadModelService:
    def __init__(self) -> None:
        self.entries = EntryService()
        self.bindings = ScopeBindingService()
        self.catalog = VariantCatalogService()
        self.binding_repo = self.bindings.bindings
        self.variant_repo = self.catalog.variants

    def branch_summary(self, project_id: int = DEFAULT_PROJECT_ID, lang: str | None = None) -> dict[str, Any]:
        rel_branch = BranchRef.rel_current()
        rel_projection = self._branch_projection_map(rel_branch, project_id, lang)
        branches = [
            {
                "branch_ref": str(rel_branch),
                "entry_count": len(rel_projection),
                "status_counts": {
                    "aligned": len(rel_projection),
                    "diverged": 0,
                    "base_only": 0,
                    "target_only": 0,
                },
            }
        ]
        for version in self._list_dev_versions(project_id=project_id, active_only=True):
            branch_ref = BranchRef.dev(version["version"])
            members = self._branch_projection_map(branch_ref, project_id, lang)
            compare = self._build_compare_rows(rel_projection, members, lang)
            branches.append(
                {
                    "branch_ref": str(branch_ref),
                    "entry_count": len(members),
                    "status_counts": compare["status_counts"],
                    "version_series": version["version_series"],
                    "is_candidate_release": version["is_candidate_release"],
                }
            )
        return {"branches": branches}

    def compare_branches(
        self,
        base_branch_ref: BranchRef,
        target_branch_ref: BranchRef,
        project_id: int = DEFAULT_PROJECT_ID,
        lang: str | None = None,
        search: str | None = None,
        states: list[str] | None = None,
        diff_categories: list[str] | None = None,
        priority_statuses: list[str] | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        base_projection = self._branch_projection_map(base_branch_ref, project_id, lang)
        target_projection = self._branch_projection_map(target_branch_ref, project_id, lang)
        compare = self._build_compare_rows(
            base_projection,
            target_projection,
            lang,
            search=search,
            states=states,
            diff_categories=diff_categories,
            priority_statuses=priority_statuses,
            page=page,
            page_size=page_size,
            project_id=project_id,
            base_branch_ref=base_branch_ref,
            target_branch_ref=target_branch_ref,
        )
        compare["base_branch_ref"] = str(base_branch_ref)
        compare["target_branch_ref"] = str(target_branch_ref)
        return compare

    def translation_queue(
        self,
        target_branch_ref: BranchRef,
        project_id: int = DEFAULT_PROJECT_ID,
        lang: str | None = None,
        search: str | None = None,
        priority_statuses: list[str] | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        compare = self.compare_branches(
            BranchRef.rel_current(),
            target_branch_ref,
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
            "target_branch_ref": str(target_branch_ref),
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
                    "branch_ref": f"{binding['scope_type']}/{binding['scope_value']}",
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
        results = [
            self._search_row(item)
            for item in self.binding_repo.search_active_by_source(
                project_id,
                source,
                self.variant_repo,
            )
        ]
        return {"source": source, "results": results}

    def _branch_projection_map(
        self,
        branch_ref: BranchRef,
        project_id: int,
        lang: str | None,
    ) -> dict[str, dict[str, Any]]:
        scope_type, scope_value = branch_ref.as_tuple()
        return {
            item["business_key"]: item
            for item in self.binding_repo.list_scope_projection(project_id, scope_type, scope_value, lang)
        }

    def _search_row(self, item: dict[str, Any]) -> dict[str, Any]:
        variant = item["variant"]
        return {
            "business_key": item["business_key"],
            "branch_ref": f"{item['scope_type']}/{item['scope_value']}",
            "variant_id": int(variant["variant_id"]),
            "file_name": variant["file_name"],
            "source": variant["source"],
            "translations": variant["translations"],
            "remarks": variant["remarks"],
        }

    def _build_compare_rows(
        self,
        base_map: dict[str, dict[str, Any]],
        target_map: dict[str, dict[str, Any]],
        lang: str | None,
        *,
        search: str | None = None,
        states: list[str] | None = None,
        diff_categories: list[str] | None = None,
        priority_statuses: list[str] | None = None,
        page: int = 1,
        page_size: int | None = None,
        project_id: int | None = None,
        base_branch_ref: BranchRef | None = None,
        target_branch_ref: BranchRef | None = None,
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
                    "base_projection": base_item,
                    "target_projection": target_item,
                }
            )

        filtered_rows = self._filter_compare_rows(
            all_rows,
            search=search,
            states=states,
            diff_filter=diff_categories,
            priority_statuses=priority_statuses,
        )
        filtered_priority_rows = [self._priority_row(row, lang) for row in filtered_rows]
        full_priority_rows = [self._priority_row(row, lang) for row in all_rows]
        page_value, page_size_value, paged_rows_meta = self._paginate(filtered_rows, page, page_size)
        _, _, paged_priority_rows = self._paginate(filtered_priority_rows, page, page_size)

        paged_rows = paged_rows_meta
        if (
            project_id is not None
            and base_branch_ref is not None
            and target_branch_ref is not None
        ):
            page_keys = [row["business_key"] for row in paged_rows_meta]
            base_scope_type, base_scope_value = base_branch_ref.as_tuple()
            base_full_map = {
                item["business_key"]: item
                for item in self.binding_repo.list_scope_entries_for_keys(
                    project_id,
                    base_scope_type,
                    base_scope_value,
                    page_keys,
                    self.variant_repo,
                )
            }
            target_scope_type, target_scope_value = target_branch_ref.as_tuple()
            target_full_map = {
                item["business_key"]: item
                for item in self.binding_repo.list_scope_entries_for_keys(
                    project_id,
                    target_scope_type,
                    target_scope_value,
                    page_keys,
                    self.variant_repo,
                )
            }
            paged_rows = [
                {
                    "business_key": row["business_key"],
                    "state": row["state"],
                    "diff_categories": row["diff_categories"],
                    "priority_status": row["priority_status"],
                    "base": self._compare_side(base_full_map.get(row["business_key"])),
                    "target": self._compare_side(target_full_map.get(row["business_key"])),
                }
                for row in paged_rows_meta
            ]

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

    def _priority_row(self, row: dict[str, Any], lang: str | None) -> dict[str, Any]:
        target = row["target_projection"]
        base = row["base_projection"]
        preferred = target or base
        return {
            "business_key": row["business_key"],
            "priority_status": row["priority_status"],
            "state": row["state"],
            "diff_categories": row["diff_categories"],
            "file_name": preferred["file_name"] if preferred else None,
            "source": preferred["source"] if preferred else "",
            "target_text": preferred["lang_target_text"] if preferred and lang is not None else "",
        }

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

    def _compare_side(self, item: dict[str, Any] | None) -> dict[str, Any] | None:
        if item is None:
            return None
        variant = item["variant"]
        return {
            "branch_ref": f"{item['scope_type']}/{item['scope_value']}",
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
        diff_categories: list[str] = []
        if base_item["source"] != target_item["source"]:
            diff_categories.append("source_changed")
        if base_item["translations_fingerprint"] != target_item["translations_fingerprint"]:
            diff_categories.append("translation_changed")
        if base_item["remarks_fingerprint"] != target_item["remarks_fingerprint"]:
            diff_categories.append("remark_changed")
        if base_item["file_name"] != target_item["file_name"]:
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
        base_target = self._lang_value(base_item)
        target_target = self._lang_value(target_item)
        if state == "diverged" and "source_changed" in diff_categories:
            return "source_mismatch"
        if state == "base_only":
            return "fillable" if base_target else "needs_translation"
        if state == "target_only":
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

    def _lang_value(self, item: dict[str, Any] | None) -> str:
        if item is None:
            return ""
        return item["lang_target_text"]

    def _list_dev_versions(
        self,
        project_id: int,
        active_only: bool,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT version, version_line, is_candidate_release
            FROM dev_versions
            WHERE project_id = ?
        """
        params: list[Any] = [project_id]
        if active_only:
            query += " AND promoted_at IS NULL"
        query += " ORDER BY created_at DESC, version DESC"
        with get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "version": row["version"],
                "version_series": row["version_line"],
                "is_candidate_release": bool(row["is_candidate_release"]),
            }
            for row in rows
        ]
