from __future__ import annotations

from typing import Any
from time import perf_counter

from app.db import get_conn, json_loads
from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.io import normalize_content_map, normalize_non_content_map, normalize_non_content_value
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
        variants_by_entry = self.catalog.list_variants_for_entries(entry_ids, include_trashed=False)
        binding_rows_by_entry = {
            entry_id: self.bindings.list_bindings_for_entry(entry_id)
            for entry_id in entry_ids
        }

        counts = {
            "created_entry_count": len(set(missing_entry_keys)),
            "created_source_variant_count": 0,
            "bound_rel_owned_source_variant_count": 0,
            "updated_reused_source_variant_count": 0,
            "revived_orphan_source_variant_count": 0,
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
                binding_rows_by_entry,
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
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
    ) -> str:
        bindings = binding_rows_by_entry.get(entry_id, [])
        variants = variants_by_entry.get(entry_id, [])
        current_dev = self._find_binding(bindings, "dev", version)
        source_variant = self._find_source_variant_in_cache(entry_id, variants, payload["source"])

        if source_variant is None:
            variant_id = self.catalog.create_variant(
                entry_id,
                file_name=payload.get("file_name"),
                source=payload["source"],
                translations=payload.get("translations", {}),
                remarks=payload.get("remarks", {}),
            )
            self.bindings.bind_scope(entry_id, "dev", version, variant_id)
            counts["created_source_variant_count"] += 1
            self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry)
            return "CREATED_SOURCE_VARIANT"

        variant_id = int(source_variant["variant_id"])
        rel_bound = self._is_rel_bound(bindings, variant_id)
        binding_count = self._binding_count(bindings, variant_id)
        payload_matches = self._payload_matches_variant(source_variant, payload)

        if rel_bound:
            if current_dev is not None and int(current_dev["variant_id"]) == variant_id:
                counts["noop_count"] += 1
                return "NOOP_ALREADY_MATCHED"
            self.bindings.bind_scope(entry_id, "dev", version, variant_id)
            counts["bound_rel_owned_source_variant_count"] += 1
            self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry)
            return "BOUND_REL_OWNED_SOURCE_VARIANT"

        if binding_count > 0:
            if payload_matches and current_dev is not None and int(current_dev["variant_id"]) == variant_id:
                counts["noop_count"] += 1
                return "NOOP_ALREADY_MATCHED"
            self.catalog.update_variant(
                variant_id,
                file_name=payload.get("file_name"),
                source=payload["source"],
                translations=payload.get("translations", {}),
                remarks=payload.get("remarks", {}),
            )
            self.bindings.bind_scope(entry_id, "dev", version, variant_id)
            counts["updated_reused_source_variant_count"] += 1
            self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry)
            return "UPDATED_REUSED_SOURCE_VARIANT"

        self.catalog.update_variant(
            variant_id,
            file_name=payload.get("file_name"),
            source=payload["source"],
            translations=payload.get("translations", {}),
            remarks=payload.get("remarks", {}),
        )
        self.bindings.bind_scope(entry_id, "dev", version, variant_id)
        counts["revived_orphan_source_variant_count"] += 1
        self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry)
        return "REVIVED_ORPHAN_SOURCE_VARIANT"

    def _refresh_entry_cache(
        self,
        entry_id: int,
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
    ) -> None:
        binding_rows_by_entry[entry_id] = self.bindings.list_bindings_for_entry(entry_id)
        variants_by_entry[entry_id] = self.catalog.list_variants(entry_id, include_trashed=False)

    def _find_binding(
        self,
        bindings: list[dict[str, Any]],
        scope_type: str,
        scope_value: str,
    ) -> dict[str, Any] | None:
        for binding in bindings:
            if binding["scope_type"] == scope_type and binding["scope_value"] == scope_value:
                return binding
        return None

    def _find_source_variant_in_cache(
        self,
        entry_id: int,
        variants: list[dict[str, Any]],
        source: str,
    ) -> dict[str, Any] | None:
        normalized_source = normalize_non_content_value(source)
        candidates = [variant for variant in variants if variant["source"] == normalized_source]
        if not candidates:
            return None
        if len(candidates) > 1:
            raise RuntimeError(
                f"duplicate active variants found for entry_id={entry_id}, source={normalized_source!r}"
            )
        return candidates[0]

    def _is_rel_bound(self, bindings: list[dict[str, Any]], variant_id: int) -> bool:
        return any(
            int(binding["variant_id"]) == variant_id
            and binding["scope_type"] == "rel"
            and binding["scope_value"] == "current"
            for binding in bindings
        )

    def _binding_count(self, bindings: list[dict[str, Any]], variant_id: int) -> int:
        return sum(1 for binding in bindings if int(binding["variant_id"]) == variant_id)

    def _payload_matches_variant(
        self,
        variant: dict[str, Any],
        payload: dict[str, Any],
    ) -> bool:
        return (
            variant["file_name"] == normalize_non_content_value(payload.get("file_name"))
            and variant["source"] == normalize_non_content_value(payload["source"])
            and dict(variant["translations"]) == normalize_content_map(payload.get("translations", {}))
            and dict(variant["remarks"]) == normalize_non_content_map(payload.get("remarks", {}))
        )

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
