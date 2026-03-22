from __future__ import annotations

from collections import Counter
import sqlite3
from time import perf_counter
from typing import Any

from app.db import get_conn, json_loads
from app.services.branch.models import BranchRef
from app.services.branch.policy import BranchMutationPolicy
from app.services.branch.service import BranchService
from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.io import normalize_content_map, normalize_non_content_map, normalize_non_content_value
from app.services.variant.bindings import BindingCommandService, BindingLookupService
from app.services.variant.entries import EntryService
from app.services.variant.variants import VariantCatalogService

MUTATION_STATUSES = (
    "UPDATED_BOUND_VARIANT",
    "BOUND_EXISTING_VARIANT",
    "UPDATED_AND_BOUND_EXISTING_VARIANT",
    "CREATED_AND_BOUND_VARIANT",
    "MISSING_IN_SCOPE",
    "NOOP",
)


class BranchMutationService:
    def __init__(self) -> None:
        self.branch = BranchService()
        self.entries = EntryService()
        self.catalog = VariantCatalogService()
        self.binding_commands = BindingCommandService()
        self.bindings = self.binding_commands
        self.binding_lookup = BindingLookupService()
        self.imports = ImportService()
        self.projects = ProjectService()

    def apply(
        self,
        branch_ref: BranchRef,
        input_payload: dict[str, Any],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        policy = BranchMutationPolicy.for_branch(branch_ref)
        input_kind = str(input_payload["kind"])
        policy.validate_input_kind(input_kind)
        with get_conn() as conn:
            dev_branch = None
            if branch_ref.is_dev:
                mark_as_candidate = input_payload.get("mark_as_candidate_release")
                dev_branch = self.branch.ensure_dev_branch(
                    branch_ref.branch_value,
                    mark_as_candidate,
                    project_id,
                    conn=conn,
                )
            if input_kind == "direct":
                return self._apply_direct(branch_ref, input_payload["changes"], policy, project_id, conn=conn)
            return self._apply_import_batch(
                branch_ref,
                int(input_payload["import_batch_id"]),
                bool(input_payload.get("mark_as_candidate_release", True)),
                project_id,
                conn=conn,
                version_series=(dev_branch or {}).get("version_series"),
            )

    def _apply_direct(
        self,
        branch_ref: BranchRef,
        changes: list[dict[str, Any]],
        policy: BranchMutationPolicy,
        project_id: int,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        started = perf_counter()
        status_counts: Counter[str] = Counter()
        report_rows: list[dict[str, Any]] = []
        created_entry_count = 0
        for change in changes:
            row = self._apply_direct_change(branch_ref, change, policy, project_id, conn=conn)
            created_entry_count += int(row.pop("created_entry", False))
            status_counts.update([row["status"]])
            report_rows.append(row)
        summary = {
            "branch_ref": str(branch_ref),
            "input_kind": "direct",
            "processed_count": len(report_rows),
            "created_entry_count": created_entry_count,
            **self._status_summary(status_counts),
            "stages": [
                {
                    "stage": "apply_scope_mutation",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {
                        "branch_ref": str(branch_ref),
                        "input_kind": "direct",
                        "processed_count": len(report_rows),
                    },
                }
            ],
        }
        return {"summary": summary, "report_rows": report_rows}

    def _apply_import_batch(
        self,
        branch_ref: BranchRef,
        import_batch_id: int,
        mark_as_candidate_release: bool,
        project_id: int,
        conn: sqlite3.Connection,
        version_series: str | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        self.imports.require_batch_project(import_batch_id, project_id)
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
        existing_entries_by_key = self.entries.get_entries_by_keys(business_keys, project_id=project_id, conn=conn)
        missing_entry_keys = {key for key in business_keys if key not in existing_entries_by_key}
        entries_by_key = self.entries.ensure_entries(business_keys, project_id=project_id, conn=conn)
        entry_ids = [int(entry["entry_id"]) for entry in entries_by_key.values()]
        variants_by_entry = self.catalog.list_variants_for_entries(entry_ids, include_trashed=False, conn=conn)
        binding_rows_by_entry = {
            entry_id: self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn)
            for entry_id in entry_ids
        }

        status_counts: Counter[str] = Counter()
        report_rows: list[dict[str, Any]] = []
        for row in payload_rows:
            payload = row["payload"]
            entry = entries_by_key[payload["business_key"]]
            entry_id = int(entry["entry_id"])
            variants_by_entry.setdefault(entry_id, [])
            status = self._apply_import_row_cached(
                entry_id,
                payload,
                branch_ref,
                binding_rows_by_entry,
                variants_by_entry,
                conn=conn,
            )
            status_counts.update([status])
            report_rows.append(
                {
                    "business_key": payload["business_key"],
                    "file_path": row["file_path"],
                    "sheet_name": row["sheet_name"],
                    "row_index": row["row_index"],
                    "status": status,
                }
            )

        summary = {
            "branch_ref": str(branch_ref),
            "input_kind": "import_batch",
            "import_batch_id": import_batch_id,
            "mark_as_candidate_release": mark_as_candidate_release,
            "version_series": version_series,
            "processed_count": len(report_rows),
            "created_entry_count": len(set(missing_entry_keys)),
            **self._status_summary(status_counts),
            "stages": [
                {
                    "stage": "apply_scope_mutation",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {
                        "branch_ref": str(branch_ref),
                        "input_kind": "import_batch",
                        "processed_count": len(report_rows),
                    },
                }
            ],
        }
        return {"summary": summary, "report_rows": report_rows}

    def _apply_direct_change(
        self,
        branch_ref: BranchRef,
        change: dict[str, Any],
        policy: BranchMutationPolicy,
        project_id: int,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        business_key = normalize_non_content_value(change.get("business_key"))
        if not business_key:
            raise ValueError("business_key is required")
        for lang in (change.get("translations_by_lang") or {}).keys():
            self.projects.require_language(lang, project_id)

        entry = self.entries.get_entry(business_key, project_id=project_id, conn=conn)
        created_entry = False
        if entry is None and change.get("source") is not None and policy.allow_missing_entry_creation():
            entry = self.entries.get_or_create_entry(business_key, project_id=project_id, conn=conn)
            created_entry = True
        if entry is None:
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "status": "MISSING_IN_SCOPE",
                "created_entry": created_entry,
            }

        entry_id = int(entry["entry_id"])
        current_binding = self.binding_lookup.get_binding(entry_id, branch_ref, conn=conn)
        current_variant = (
            self.catalog.get_variant(int(current_binding["variant_id"]), conn=conn)
            if current_binding is not None
            else None
        )
        if branch_ref.is_rel and current_variant is None:
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "status": "MISSING_IN_SCOPE",
                "created_entry": created_entry,
            }

        if change.get("source") is None:
            if current_variant is None:
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "status": "MISSING_IN_SCOPE",
                    "created_entry": created_entry,
                }
            merged = self._merged_variant_payload(current_variant, change, current_variant["source"])
            if self._variant_matches(current_variant, merged):
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": int(current_variant["variant_id"]),
                    "status": "NOOP",
                    "created_entry": created_entry,
                }
            bound_branch_refs = self._bound_branch_refs_for_variant(
                self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
                int(current_variant["variant_id"]),
            )
            if not policy.can_update_hit_variant(branch_ref, bound_branch_refs):
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": int(current_variant["variant_id"]),
                    "status": "NOOP",
                    "created_entry": created_entry,
                }
            self.catalog.update_variant(
                int(current_variant["variant_id"]),
                merged,
                conn=conn,
            )
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": int(current_variant["variant_id"]),
                "status": "UPDATED_BOUND_VARIANT",
                "created_entry": created_entry,
            }

        requested_source = normalize_non_content_value(change.get("source"))
        if not requested_source:
            raise ValueError("source is required")
        if current_variant is not None and requested_source == current_variant["source"]:
            merged = self._merged_variant_payload(current_variant, change, requested_source)
            if self._variant_matches(current_variant, merged):
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": int(current_variant["variant_id"]),
                    "status": "NOOP",
                    "created_entry": created_entry,
                }
            bound_branch_refs = self._bound_branch_refs_for_variant(
                self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
                int(current_variant["variant_id"]),
            )
            if not policy.can_update_hit_variant(branch_ref, bound_branch_refs):
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": int(current_variant["variant_id"]),
                    "status": "NOOP",
                    "created_entry": created_entry,
                }
            self.catalog.update_variant(
                int(current_variant["variant_id"]),
                merged,
                conn=conn,
            )
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": int(current_variant["variant_id"]),
                "status": "UPDATED_BOUND_VARIANT",
                "created_entry": created_entry,
            }

        target_variant = self.catalog.find_variant_by_source(
            entry_id,
            requested_source,
            include_trashed=False,
            conn=conn,
        )
        content_base = current_variant or target_variant
        merged = self._merged_variant_payload(content_base, change, requested_source)
        if target_variant is None:
            if current_variant is None and not policy.allow_missing_entry_creation():
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "status": "MISSING_IN_SCOPE",
                    "created_entry": created_entry,
                }
            variant_id = self.catalog.create_variant(
                entry_id,
                merged,
                conn=conn,
            )
            self.binding_commands.bind_scope(entry_id, branch_ref, variant_id, conn=conn)
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": variant_id,
                "status": "CREATED_AND_BOUND_VARIANT",
                "created_entry": created_entry,
            }

        target_variant_id = int(target_variant["variant_id"])
        current_matches_target = current_binding is not None and int(current_binding["variant_id"]) == target_variant_id
        bound_branch_refs = self._bound_branch_refs_for_variant(
            self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
            target_variant_id,
        )
        if not policy.can_update_hit_variant(branch_ref, bound_branch_refs):
            if current_matches_target:
                return {
                    "business_key": business_key,
                    "branch_ref": str(branch_ref),
                    "variant_id": target_variant_id,
                    "status": "NOOP",
                    "created_entry": created_entry,
                }
            self.binding_commands.bind_scope(entry_id, branch_ref, target_variant_id, conn=conn)
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": target_variant_id,
                "status": "BOUND_EXISTING_VARIANT",
                "created_entry": created_entry,
            }

        payload_matches_target = self._variant_matches(target_variant, merged)
        if current_matches_target and payload_matches_target:
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": target_variant_id,
                "status": "NOOP",
                "created_entry": created_entry,
            }
        if payload_matches_target:
            self.binding_commands.bind_scope(entry_id, branch_ref, target_variant_id, conn=conn)
            return {
                "business_key": business_key,
                "branch_ref": str(branch_ref),
                "variant_id": target_variant_id,
                "status": "BOUND_EXISTING_VARIANT",
                "created_entry": created_entry,
            }

        self.catalog.update_variant(
            target_variant_id,
            merged,
            conn=conn,
        )
        if not current_matches_target:
            self.binding_commands.bind_scope(entry_id, branch_ref, target_variant_id, conn=conn)
            status = "UPDATED_AND_BOUND_EXISTING_VARIANT"
        else:
            status = "UPDATED_BOUND_VARIANT"
        return {
            "business_key": business_key,
            "branch_ref": str(branch_ref),
            "variant_id": target_variant_id,
            "status": status,
            "created_entry": created_entry,
        }

    def _apply_import_row_cached(
        self,
        entry_id: int,
        payload: dict[str, Any],
        target_branch: BranchRef,
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
        conn: sqlite3.Connection,
    ) -> str:
        bindings = binding_rows_by_entry.get(entry_id, [])
        variants = variants_by_entry.get(entry_id, [])
        current_binding = self._find_binding(bindings, target_branch)
        source_variant = self._find_source_variant_in_cache(entry_id, variants, payload["source"])

        if source_variant is None:
            variant_id = self.catalog.create_variant(
                entry_id,
                self.catalog.build_content(
                    payload.get("file_name"),
                    payload["source"],
                    payload.get("translations", {}),
                    payload.get("remarks", {}),
                ),
                conn=conn,
            )
            self.binding_commands.bind_scope(entry_id, target_branch, variant_id, conn=conn)
            self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry, conn=conn)
            return "CREATED_AND_BOUND_VARIANT"

        variant_id = int(source_variant["variant_id"])
        current_matches = current_binding is not None and int(current_binding["variant_id"]) == variant_id
        bound_branch_refs = self._bound_branch_refs_for_variant(bindings, variant_id)
        if not BranchMutationPolicy.for_branch(target_branch).can_update_hit_variant(target_branch, bound_branch_refs):
            if current_matches:
                return "NOOP"
            self.binding_commands.bind_scope(entry_id, target_branch, variant_id, conn=conn)
            self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry, conn=conn)
            return "BOUND_EXISTING_VARIANT"

        payload_matches = self._payload_matches_variant(source_variant, payload)
        if payload_matches:
            if current_matches:
                return "NOOP"
            self.binding_commands.bind_scope(entry_id, target_branch, variant_id, conn=conn)
            self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry, conn=conn)
            return "BOUND_EXISTING_VARIANT"

        self.catalog.update_variant(
            variant_id,
            self.catalog.build_content(
                payload.get("file_name"),
                payload["source"],
                payload.get("translations", {}),
                payload.get("remarks", {}),
            ),
            conn=conn,
        )
        if current_matches:
            status = "UPDATED_BOUND_VARIANT"
        else:
            self.binding_commands.bind_scope(entry_id, target_branch, variant_id, conn=conn)
            status = "UPDATED_AND_BOUND_EXISTING_VARIANT"
        self._refresh_entry_cache(entry_id, binding_rows_by_entry, variants_by_entry, conn=conn)
        return status

    def _merged_variant_payload(
        self,
        base_variant: dict[str, Any] | None,
        change: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        translations = dict(base_variant["translations"]) if base_variant is not None else {}
        translations.update(change.get("translations_by_lang", {}))
        remarks = dict(base_variant["remarks"]) if base_variant is not None else {}
        remarks.update(change.get("remarks_by_key", {}))
        if change.get("file_name") is not None:
            file_name = change.get("file_name")
        elif base_variant is not None:
            file_name = base_variant["file_name"]
        else:
            file_name = None
        return {
            "file_name": normalize_non_content_value(file_name),
            "source": normalize_non_content_value(source),
            "translations": normalize_content_map(translations),
            "remarks": normalize_non_content_map(remarks),
        }

    def _variant_matches(self, variant: dict[str, Any], payload: dict[str, Any]) -> bool:
        return (
            variant["file_name"] == payload["file_name"]
            and variant["source"] == payload["source"]
            and dict(variant["translations"]) == payload["translations"]
            and dict(variant["remarks"]) == payload["remarks"]
        )

    def _status_summary(self, status_counts: Counter[str]) -> dict[str, int]:
        return {
            "updated_bound_variant_count": status_counts["UPDATED_BOUND_VARIANT"],
            "bound_existing_variant_count": status_counts["BOUND_EXISTING_VARIANT"],
            "updated_and_bound_existing_variant_count": status_counts["UPDATED_AND_BOUND_EXISTING_VARIANT"],
            "created_and_bound_variant_count": status_counts["CREATED_AND_BOUND_VARIANT"],
            "missing_in_scope_count": status_counts["MISSING_IN_SCOPE"],
            "noop_count": status_counts["NOOP"],
        }

    def _refresh_entry_cache(
        self,
        entry_id: int,
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
        conn: sqlite3.Connection,
    ) -> None:
        binding_rows_by_entry[entry_id] = self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn)
        variants_by_entry[entry_id] = self.catalog.list_variants(entry_id, include_trashed=False, conn=conn)

    def _find_binding(self, bindings: list[dict[str, Any]], branch_ref: BranchRef) -> dict[str, Any] | None:
        scope_type, scope_value = branch_ref.as_tuple()
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

    def _bound_branch_refs_for_variant(self, bindings: list[dict[str, Any]], variant_id: int) -> list[BranchRef]:
        return [
            BranchRef.parse(f"{binding['scope_type']}/{binding['scope_value']}")
            for binding in bindings
            if int(binding["variant_id"]) == variant_id
        ]

    def _payload_matches_variant(self, variant: dict[str, Any], payload: dict[str, Any]) -> bool:
        normalized_payload = self.catalog.build_content(
            payload.get("file_name"),
            payload["source"],
            payload.get("translations", {}),
            payload.get("remarks", {}),
        )
        return (
            variant["file_name"] == normalized_payload["file_name"]
            and variant["source"] == normalized_payload["source"]
            and dict(variant["translations"]) == normalized_payload["translations"]
            and dict(variant["remarks"]) == normalized_payload["remarks"]
        )
