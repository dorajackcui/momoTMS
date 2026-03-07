from __future__ import annotations

from typing import Any
from time import perf_counter

from app.db import get_conn, json_loads
from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.utils import now_iso
from app.services.variant.services import EntryService, ScopeBindingService, VariantCatalogService


class DevVersionService:
    def __init__(self) -> None:
        self.imports = ImportService()
        self.entries = EntryService()
        self.catalog = VariantCatalogService()
        self.bindings = ScopeBindingService()

    def ensure_version(
        self,
        version: str,
        mark_as_candidate: bool,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        version_line = self._version_line(version)
        with get_conn() as conn:
            if mark_as_candidate:
                conn.execute(
                    "UPDATE dev_versions SET is_candidate_release = 0 WHERE project_id = ?",
                    (project_id,),
                )
            conn.execute(
                """
                INSERT INTO dev_versions(
                    project_id,
                    version,
                    version_line,
                    is_candidate_release,
                    created_at,
                    promoted_at
                )
                VALUES (?, ?, ?, ?, ?, NULL)
                ON CONFLICT(project_id, version)
                DO UPDATE SET
                    version_line = excluded.version_line,
                    is_candidate_release = excluded.is_candidate_release
                """,
                (
                    project_id,
                    version,
                    version_line,
                    1 if mark_as_candidate else 0,
                    now_iso(),
                ),
            )
        return {
            "project_id": project_id,
            "version": version,
            "version_line": version_line,
            "is_candidate_release": mark_as_candidate,
        }

    def import_batch(
        self,
        import_batch_id: int,
        version: str,
        mark_as_candidate: bool = True,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        bind_started = perf_counter()
        version_info = self.ensure_version(version, mark_as_candidate, project_id)
        self.imports.require_batch_project(import_batch_id, project_id)
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT import_row_id, file_path, sheet_name, row_index, payload_json
                FROM import_rows
                WHERE import_batch_id = ? AND status = 'ok'
                ORDER BY import_row_id
                """,
                (import_batch_id,),
            ).fetchall()

        payload_rows = [
            {
                "import_row_id": int(row["import_row_id"]),
                "file_path": row["file_path"],
                "sheet_name": row["sheet_name"],
                "row_index": int(row["row_index"]),
                "payload": json_loads(row["payload_json"]),
            }
            for row in rows
        ]
        business_keys = [row["payload"]["business_key"] for row in payload_rows]
        existing_entries_by_key = self.entries.get_entries_by_keys(business_keys, project_id=project_id)
        missing_entry_keys = {key for key in business_keys if key not in existing_entries_by_key}
        entries_by_key = self.entries.ensure_entries(business_keys, project_id=project_id)

        entry_ids = [int(entry["entry_id"]) for entry in entries_by_key.values()]
        current_dev_by_entry = self.bindings.get_bindings_for_entries(entry_ids, "dev", version)
        current_rel_by_entry = self.bindings.get_bindings_for_entries(entry_ids, "rel", "current")
        variants_by_entry = self.catalog.list_variants_for_entries(entry_ids, include_trashed=False)

        counts = {
            "created_entry_count": len(set(missing_entry_keys)),
            "created_variant_count": 0,
            "updated_bound_variant_count": 0,
            "reused_rel_variant_count": 0,
            "rebound_variant_count": 0,
            "noop_count": 0,
        }
        report_rows: list[dict[str, Any]] = []
        for row in payload_rows:
            payload = row["payload"]
            business_key = payload["business_key"]
            entry = entries_by_key[business_key]
            entry_id = int(entry["entry_id"])
            variants_by_entry.setdefault(entry_id, [])
            status = self._apply_import_row_cached(
                entry_id,
                payload,
                version,
                counts,
                current_dev_by_entry,
                current_rel_by_entry,
                variants_by_entry,
            )
            report_rows.append(
                {
                    "business_key": business_key,
                    "file_path": row["file_path"],
                    "sheet_name": row["sheet_name"],
                    "row_index": row["row_index"],
                    "status": status,
                }
            )

        summary = {
            "import_batch_id": import_batch_id,
            "version": version,
            "version_line": version_info["version_line"],
            "is_candidate_release": mark_as_candidate,
            **counts,
            "processed_count": len(report_rows),
            "stages": [
                {
                    "stage": "bind_dev_scope",
                    "elapsed_ms": int((perf_counter() - bind_started) * 1000),
                    "meta": {
                        "version": version,
                        "processed_count": len(report_rows),
                    },
                }
            ],
        }
        return {"summary": summary, "report_rows": report_rows}

    def list_versions(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT version, version_line, is_candidate_release, created_at, promoted_at
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
                "project_id": project_id,
                "version": row["version"],
                "version_line": row["version_line"],
                "is_candidate_release": bool(row["is_candidate_release"]),
                "member_count": self.bindings.count_scope("dev", row["version"], project_id),
                "created_at": row["created_at"],
                "promoted_at": row["promoted_at"],
            }
            for row in rows
        ]

    def get_version(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        for version_info in self.list_versions(project_id=project_id, active_only=False):
            if version_info["version"] == version:
                version_info["members"] = [
                    self._scope_entry_to_string_detail(item)
                    for item in self.bindings.list_scope_entries("dev", version, project_id)
                ]
                return version_info
        raise KeyError(f"dev version not found: {version}")

    def get_candidate_release(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT version
                FROM dev_versions
                WHERE project_id = ? AND is_candidate_release = 1 AND promoted_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if not row:
            return None
        return self.get_version(row["version"], project_id)

    def versions_in_line(self, version_line: str, project_id: int = DEFAULT_PROJECT_ID) -> list[str]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT version
                FROM dev_versions
                WHERE project_id = ? AND version_line = ?
                ORDER BY created_at DESC
                """,
                (project_id, version_line),
            ).fetchall()
        return [row["version"] for row in rows]

    def mark_promoted(self, versions: list[str], project_id: int = DEFAULT_PROJECT_ID) -> None:
        if not versions:
            return
        placeholders = ", ".join("?" for _ in versions)
        with get_conn() as conn:
            conn.execute(
                f"""
                UPDATE dev_versions
                SET promoted_at = ?, is_candidate_release = 0
                WHERE project_id = ? AND version IN ({placeholders})
                """,
                [now_iso(), project_id, *versions],
            )

    def _apply_import_row_cached(
        self,
        entry_id: int,
        payload: dict[str, Any],
        version: str,
        counts: dict[str, int],
        current_dev_by_entry: dict[int, dict[str, Any]],
        current_rel_by_entry: dict[int, dict[str, Any]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
    ) -> str:
        current_dev = current_dev_by_entry.get(entry_id)
        current_rel = current_rel_by_entry.get(entry_id)
        desired = self._find_reusable_variant_in_cache(
            variants_by_entry.get(entry_id, []),
            payload,
        )

        if current_dev is not None:
            current_variant = self._variant_from_cache(variants_by_entry.get(entry_id, []), int(current_dev["variant_id"]))
            if desired is not None and int(desired["variant_id"]) == int(current_variant["variant_id"]):
                counts["noop_count"] += 1
                return "NOOP_ALREADY_MATCHED"
            if current_rel is not None and int(current_rel["variant_id"]) == int(current_dev["variant_id"]):
                target_variant_id = self._ensure_payload_variant_cached(
                    entry_id,
                    payload,
                    desired,
                    counts,
                    variants_by_entry,
                )
                self.bindings.bind_scope(entry_id, "dev", version, target_variant_id)
                current_dev_by_entry[entry_id] = {
                    "scope_type": "dev",
                    "scope_value": version,
                    "entry_id": entry_id,
                    "variant_id": target_variant_id,
                }
                counts["rebound_variant_count"] += 1
                return "REBOUND_FROM_REL_VARIANT"
            self.catalog.update_variant(
                int(current_dev["variant_id"]),
                file_name=payload.get("file_name"),
                source=payload["source"],
                translations=payload.get("translations", {}),
                remarks=payload.get("remarks", {}),
            )
            refreshed_variant = self.catalog.get_variant(int(current_dev["variant_id"]))
            variants_by_entry[entry_id] = self._replace_cached_variant(
                variants_by_entry.get(entry_id, []),
                refreshed_variant,
            )
            counts["updated_bound_variant_count"] += 1
            return "UPDATED_BOUND_VARIANT"

        if current_rel is not None:
            rel_variant = self._variant_from_cache(variants_by_entry.get(entry_id, []), int(current_rel["variant_id"]))
            if desired is not None and int(desired["variant_id"]) == int(rel_variant["variant_id"]):
                self.bindings.bind_scope(entry_id, "dev", version, int(rel_variant["variant_id"]))
                current_dev_by_entry[entry_id] = {
                    "scope_type": "dev",
                    "scope_value": version,
                    "entry_id": entry_id,
                    "variant_id": int(rel_variant["variant_id"]),
                }
                counts["reused_rel_variant_count"] += 1
                return "REUSED_REL_VARIANT"

        target_variant_id = self._ensure_payload_variant_cached(
            entry_id,
            payload,
            desired,
            counts,
            variants_by_entry,
        )
        self.bindings.bind_scope(entry_id, "dev", version, target_variant_id)
        current_dev_by_entry[entry_id] = {
            "scope_type": "dev",
            "scope_value": version,
            "entry_id": entry_id,
            "variant_id": target_variant_id,
        }
        if desired is not None:
            counts["rebound_variant_count"] += 1
            return "BOUND_EXISTING_VARIANT"
        return "CREATED_VARIANT"

    def _ensure_payload_variant_cached(
        self,
        entry_id: int,
        payload: dict[str, Any],
        desired: dict[str, Any] | None,
        counts: dict[str, int],
        variants_by_entry: dict[int, list[dict[str, Any]]],
    ) -> int:
        if desired is not None:
            return int(desired["variant_id"])
        variant_id = self.catalog.create_variant(
            entry_id,
            file_name=payload.get("file_name"),
            source=payload["source"],
            translations=payload.get("translations", {}),
            remarks=payload.get("remarks", {}),
        )
        counts["created_variant_count"] += 1
        variants_by_entry.setdefault(entry_id, []).append(self.catalog.get_variant(variant_id))
        return variant_id

    def _find_reusable_variant_in_cache(
        self,
        variants: list[dict[str, Any]],
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        normalized_file_name = payload.get("file_name") or ""
        normalized_source = payload["source"]
        normalized_translations = payload.get("translations", {})
        normalized_remarks = payload.get("remarks", {})
        for variant in variants:
            if variant["file_name"] != normalized_file_name:
                continue
            if variant["source"] != normalized_source:
                continue
            if dict(variant["translations"]) != dict(normalized_translations):
                continue
            if dict(variant["remarks"]) != dict(normalized_remarks):
                continue
            return variant
        return None

    def _variant_from_cache(
        self,
        variants: list[dict[str, Any]],
        variant_id: int,
    ) -> dict[str, Any]:
        for variant in variants:
            if int(variant["variant_id"]) == variant_id:
                return variant
        return self.catalog.get_variant(variant_id)

    def _replace_cached_variant(
        self,
        variants: list[dict[str, Any]],
        updated_variant: dict[str, Any],
    ) -> list[dict[str, Any]]:
        replaced = False
        next_variants: list[dict[str, Any]] = []
        for variant in variants:
            if int(variant["variant_id"]) == int(updated_variant["variant_id"]):
                next_variants.append(updated_variant)
                replaced = True
            else:
                next_variants.append(variant)
        if not replaced:
            next_variants.append(updated_variant)
        return next_variants

    def _version_line(self, version: str) -> str:
        parts = version.split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}.x"
        return f"{version}.x"

    def _scope_entry_to_string_detail(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
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
                for binding in self.bindings.list_bindings_for_entry(int(item["entry_id"]))
            ],
            "deleted_at": item["variant"]["trashed_at"],
            "trash_until": item["variant"]["trash_until"],
            "restored_at": item["variant"]["restored_at"],
            "created_at": item["variant"]["created_at"],
            "updated_at": item["variant"]["updated_at"],
        }
