from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from time import perf_counter
import sqlite3
from typing import Any

from app.db import get_conn, json_dumps, json_loads
from app.services.branch.bootstrap_preview import BootstrapPreviewService
from app.services.branch.models import BranchRef
from app.services.branch.registry import BranchRegistryService
from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.jobs import JobService
from app.services.shared.utils import now_iso
from app.services.variant.bindings import BindingLookupService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.state_coordinator import VariantStateCoordinator


class _BootstrapReportWriter:
    def __init__(
        self,
        jobs: JobService,
        job_id: int,
        *,
        collect_rows: bool,
    ) -> None:
        self._jobs = jobs
        self._job_id = job_id
        self._collect_rows = collect_rows
        self.report_path = self._jobs.artifact_path(job_id, "report.json")
        self.preview_path = self._jobs.report_preview_path(job_id)
        self.preview_rows: list[dict[str, Any]] = []
        self.report_rows: list[dict[str, Any]] | None = [] if collect_rows else None
        self._handle: Any = None
        self._first = True
        self._finalized = False

    def __enter__(self) -> _BootstrapReportWriter:
        self._handle = self.report_path.open("w", encoding="utf-8")
        self._handle.write('{"rows":[')
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def write_row(self, row: dict[str, Any]) -> None:
        if self._handle is None:
            raise RuntimeError("bootstrap report writer is not open")
        if len(self.preview_rows) < self._jobs.REPORT_PREVIEW_LIMIT:
            self.preview_rows.append(dict(row))
        if self.report_rows is not None:
            self.report_rows.append(dict(row))
        if not self._first:
            self._handle.write(",")
        self._handle.write(json.dumps(row, ensure_ascii=False))
        self._first = False

    def finalize(self, summary: dict[str, Any]) -> None:
        if self._handle is None:
            raise RuntimeError("bootstrap report writer is not open")
        if self._finalized:
            return
        self._handle.write('],"summary":')
        self._handle.write(json.dumps(summary, ensure_ascii=False))
        self._handle.write("}")
        self._handle.flush()
        self.preview_path.write_text(
            json_dumps({"summary": summary, "rows": self.preview_rows}),
            encoding="utf-8",
        )
        self._finalized = True


class BranchBootstrapService:
    READ_CHUNK_SIZE = 1000
    ALLOWED_SUMMARY_EXTRA_KEYS = frozenset({"workbook_batch_id"})

    def __init__(
        self,
        *,
        imports: ImportService | None = None,
        projects: ProjectService | None = None,
        registry: BranchRegistryService | None = None,
        entries: EntryService | None = None,
        catalog: VariantCatalogService | None = None,
        bindings: VariantStateCoordinator | None = None,
        binding_lookup: BindingLookupService | None = None,
        jobs: JobService | None = None,
    ) -> None:
        self.imports = imports or ImportService()
        self.projects = projects or ProjectService()
        self.registry = registry or BranchRegistryService()
        self.entries = entries or EntryService()
        self.catalog = catalog or VariantCatalogService()
        self.bindings = bindings or VariantStateCoordinator()
        self.binding_lookup = binding_lookup or BindingLookupService()
        self.jobs = jobs or JobService()

    def bootstrap(
        self,
        branch_ref: BranchRef,
        import_batch_id: int,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
        job_id: int | None = None,
        summary_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        summary_extra = self._validate_summary_extra(summary_extra)
        if not branch_ref.is_dev:
            raise ValueError(f"bootstrap only supports dev branches: {branch_ref}")
        self.projects.require_project(project_id)
        self.imports.require_batch_project(import_batch_id, project_id)
        with get_conn() as conn:
            self.registry.ensure_dev_branch(branch_ref.branch_value, project_id=project_id, conn=conn)
            self.registry.require_not_bootstrapped(branch_ref.branch_value, project_id=project_id, conn=conn)

        owns_job = job_id is None
        active_job_id = job_id
        if active_job_id is None:
            active_job_id = self.jobs.create_job(
                "branch_bootstrap",
                {
                    "branch_ref": str(branch_ref),
                    "input_kind": "bootstrap",
                    "import_batch_id": int(import_batch_id),
                    "project_id": int(project_id),
                },
                project_id=project_id,
            )
        try:
            with get_conn() as conn:
                branch = self.registry.ensure_dev_branch(branch_ref.branch_value, project_id=project_id, conn=conn)
                self.registry.require_not_bootstrapped(branch_ref.branch_value, project_id=project_id, conn=conn)
                with _BootstrapReportWriter(self.jobs, active_job_id, collect_rows=False) as report_writer:
                    result = self._bootstrap_in_transaction(
                        branch_ref,
                        int(import_batch_id),
                        project_id=project_id,
                        version_series=str(branch["version_series"]),
                        bootstrap_job_id=active_job_id,
                        summary_extra=summary_extra,
                        report_writer=report_writer,
                        conn=conn,
                    )
        except Exception as exc:
            if owns_job:
                self.jobs.fail_job(active_job_id, str(exc))
            raise
        result["report_rows"] = self._load_report_rows(result["report_path"])
        return result

    def preview(
        self,
        branch_ref: BranchRef,
        import_batch_id: int,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return BootstrapPreviewService(
            imports=self.imports,
            projects=self.projects,
            registry=self.registry,
            entries=self.entries,
            catalog=self.catalog,
            binding_lookup=self.binding_lookup,
        ).preview(branch_ref, import_batch_id, project_id=project_id)

    def _bootstrap_in_transaction(
        self,
        branch_ref: BranchRef,
        import_batch_id: int,
        *,
        project_id: int,
        version_series: str,
        bootstrap_job_id: int,
        summary_extra: dict[str, Any] | None,
        report_writer: _BootstrapReportWriter,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        started = perf_counter()
        scope_type, scope_value = branch_ref.as_tuple()
        timestamp = now_iso()

        # ── phase 1: bulk-bind existing variants via SQL ──
        bulk_result = self._bulk_bind_existing(
            import_batch_id,
            project_id=project_id,
            scope_type=scope_type,
            scope_value=scope_value,
            timestamp=timestamp,
            conn=conn,
        )

        # ── phase 2: incremental loop for remaining rows ──
        entries_by_key: dict[str, dict[str, Any]] = {}
        variants_by_entry: dict[int, list[dict[str, Any]]] = {}
        binding_rows_by_entry: dict[int, list[dict[str, Any]]] = {}
        created_entry_keys: set[str] = set()
        seen_business_keys: set[str] = set(bulk_result["bound_keys"])
        status_counts: Counter[str] = Counter()
        status_counts["BOUND_EXISTING_VARIANT"] = bulk_result["bound_count"]
        status_counts["DUPLICATE_KEY_IN_BOOTSTRAP"] = bulk_result["dup_count"]
        processed_count = bulk_result["bound_count"] + bulk_result["dup_count"]

        for row in bulk_result["bound_report_rows"]:
            report_writer.write_row(row)

        last_import_row_id = 0
        while True:
            chunk_rows = self._load_chunk(import_batch_id, last_import_row_id, conn=conn)
            if not chunk_rows:
                break
            last_import_row_id = chunk_rows[-1]["import_row_id"]
            remainder = [
                row for row in chunk_rows
                if row["business_key"] not in seen_business_keys
            ]
            if not remainder:
                continue
            self._prime_chunk_cache(
                remainder,
                project_id=project_id,
                conn=conn,
                entries_by_key=entries_by_key,
                variants_by_entry=variants_by_entry,
                binding_rows_by_entry=binding_rows_by_entry,
                created_entry_keys=created_entry_keys,
            )
            touched_entry_ids: set[int] = set()
            for row in remainder:
                status = self._apply_row_cached(
                    row,
                    branch_ref,
                    seen_business_keys=seen_business_keys,
                    entries_by_key=entries_by_key,
                    variants_by_entry=variants_by_entry,
                    binding_rows_by_entry=binding_rows_by_entry,
                    touched_entry_ids=touched_entry_ids,
                    conn=conn,
                )
                processed_count += 1
                status_counts.update([status])
                report_writer.write_row(
                    {
                        "business_key": row["business_key"],
                        "file_path": row["file_path"],
                        "sheet_name": row["sheet_name"],
                        "row_index": row["row_index"],
                        "status": status,
                    }
                )
            if touched_entry_ids:
                self.bindings.refresh_orphan_states(list(touched_entry_ids), conn=conn)

        branch_metadata = self.registry.mark_bootstrapped(
            branch_ref.branch_value,
            bootstrap_job_id=bootstrap_job_id,
            bootstrap_import_batch_id=import_batch_id,
            project_id=project_id,
            conn=conn,
        )
        summary = {
            "branch_ref": str(branch_ref),
            "input_kind": "bootstrap",
            "import_batch_id": import_batch_id,
            "version_series": version_series,
            "processed_count": processed_count,
            "bound_existing_variant_count": status_counts["BOUND_EXISTING_VARIANT"],
            "created_and_bound_variant_count": status_counts["CREATED_AND_BOUND_VARIANT"],
            "invalid_row_count": status_counts["INVALID_ROW"],
            "duplicate_key_count": status_counts["DUPLICATE_KEY_IN_BOOTSTRAP"],
            "created_entry_count": len(created_entry_keys),
            "created_variant_count": status_counts["CREATED_AND_BOUND_VARIANT"],
            "bootstrap_state": branch_metadata["bootstrap_state"],
            "bootstrapped_at": branch_metadata["bootstrapped_at"],
            "bootstrap_job_id": branch_metadata["bootstrap_job_id"],
            "bootstrap_import_batch_id": branch_metadata["bootstrap_import_batch_id"],
            "stages": [
                {
                    "stage": "bulk_bind_existing",
                    "elapsed_ms": bulk_result["elapsed_ms"],
                    "meta": {"bound_count": bulk_result["bound_count"]},
                },
                {
                    "stage": "apply_branch_bootstrap",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {
                        "branch_ref": str(branch_ref),
                        "input_kind": "bootstrap",
                        "processed_count": processed_count,
                    },
                },
            ],
        }
        if summary_extra:
            collisions = sorted(set(summary_extra).intersection(summary))
            if collisions:
                joined = ", ".join(collisions)
                raise ValueError(f"bootstrap summary_extra cannot override summary fields: {joined}")
            summary.update(summary_extra)
        report_writer.finalize(summary)
        self._complete_job_in_transaction(
            bootstrap_job_id,
            summary=summary,
            report_path=str(report_writer.report_path),
            conn=conn,
        )
        return {
            "summary": summary,
            "report_path": str(report_writer.report_path),
        }

    def _bulk_bind_existing(
        self,
        import_batch_id: int,
        *,
        project_id: int,
        scope_type: str,
        scope_value: str,
        timestamp: str,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        """Bulk-bind import rows that match existing active variants via SQL JOIN.

        For each valid import row where (business_key, source) matches an
        existing non-trashed variant under the same project, insert a
        scope_binding and clear orphaned_at — all in bulk SQL instead of
        per-row Python.

        Returns the set of business_keys handled so the incremental loop
        can skip them.
        """
        started = perf_counter()

        # Step 1: collect the minimum import_row_id per (business_key, source)
        # from valid ok rows. This gives us the first-seen row per key without
        # an expensive window function.
        # import_rows.business_key and .source are already normalised by the parser.
        conn.execute(
            """
            CREATE TEMP TABLE _bulk_first AS
            SELECT
                MIN(ir.import_row_id) AS import_row_id,
                ir.business_key,
                ir.source
            FROM import_rows ir
            WHERE ir.import_batch_id = ?
              AND ir.status = 'ok'
              AND ir.business_key != ''
              AND ir.business_key IS NOT NULL
              AND ir.source != ''
              AND ir.source IS NOT NULL
            GROUP BY ir.business_key
            """,
            (import_batch_id,),
        )

        # Step 2: join to entries + active variants to get existing matches
        conn.execute(
            """
            CREATE TEMP TABLE _bulk_matched AS
            SELECT
                bf.import_row_id,
                ir.file_path,
                ir.sheet_name,
                ir.row_index,
                bf.business_key,
                bf.source,
                e.entry_id,
                v.variant_id
            FROM _bulk_first bf
            JOIN import_rows ir ON ir.import_row_id = bf.import_row_id
            JOIN entries e
              ON e.project_id = ? AND e.business_key = bf.business_key
            JOIN variants v
              ON v.entry_id = e.entry_id
             AND v.source = bf.source
             AND v.trashed_at IS NULL
            """,
            (project_id,),
        )

        # Step 3: bulk insert scope_bindings
        conn.execute(
            """
            INSERT OR IGNORE INTO scope_bindings(
                scope_type, scope_value, entry_id, variant_id, created_at, updated_at
            )
            SELECT ?, ?, entry_id, variant_id, ?, ?
            FROM _bulk_matched
            """,
            (scope_type, scope_value, timestamp, timestamp),
        )

        # Step 4: clear orphaned_at for bound variants
        conn.execute(
            """
            UPDATE variants
            SET orphaned_at = NULL, updated_at = ?
            WHERE variant_id IN (SELECT variant_id FROM _bulk_matched)
              AND orphaned_at IS NOT NULL
            """,
            (timestamp,),
        )

        # Index on business_key so the duplicate-row query (step 6) can
        # hash-join instead of doing a 34K × 27K nested-loop scan.
        conn.execute("CREATE INDEX _idx_bm_bk ON _bulk_matched(business_key)")

        # Step 5: fetch matched rows for report
        matched_rows = conn.execute(
            """
            SELECT import_row_id, file_path, sheet_name, row_index, business_key
            FROM _bulk_matched
            ORDER BY import_row_id
            """
        ).fetchall()

        bound_keys: set[str] = set()
        report_rows: list[dict[str, Any]] = []
        for row in matched_rows:
            bk = row["business_key"]
            bound_keys.add(bk)
            report_rows.append({
                "business_key": bk,
                "file_path": row["file_path"],
                "sheet_name": row["sheet_name"],
                "row_index": int(row["row_index"]),
                "status": "BOUND_EXISTING_VARIANT",
            })

        # Step 6: collect duplicate-key rows only for keys that were bulk-bound.
        # Rows whose first occurrence didn't match go through the incremental
        # loop, which deduplicates via seen_business_keys as before.
        if bound_keys:
            dup_rows = conn.execute(
                """
                SELECT ir.import_row_id, ir.file_path, ir.sheet_name,
                       ir.row_index, ir.business_key
                FROM import_rows ir
                JOIN _bulk_matched bm ON bm.business_key = ir.business_key
                WHERE ir.import_batch_id = ?
                  AND ir.import_row_id != bm.import_row_id
                  AND ir.status = 'ok'
                ORDER BY ir.import_row_id
                """,
                (import_batch_id,),
            ).fetchall()
            for row in dup_rows:
                bound_keys.add(row["business_key"])
                report_rows.append({
                    "business_key": row["business_key"],
                    "file_path": row["file_path"],
                    "sheet_name": row["sheet_name"],
                    "row_index": int(row["row_index"]),
                    "status": "DUPLICATE_KEY_IN_BOOTSTRAP",
                })

        conn.execute("DROP TABLE IF EXISTS _bulk_matched")
        conn.execute("DROP TABLE IF EXISTS _bulk_first")

        elapsed_ms = int((perf_counter() - started) * 1000)
        bound_count = sum(1 for r in report_rows if r["status"] == "BOUND_EXISTING_VARIANT")
        dup_count = sum(1 for r in report_rows if r["status"] == "DUPLICATE_KEY_IN_BOOTSTRAP")
        return {
            "bound_count": bound_count,
            "dup_count": dup_count,
            "bound_keys": bound_keys,
            "bound_report_rows": report_rows,
            "elapsed_ms": elapsed_ms,
        }

    def _load_chunk(
        self,
        import_batch_id: int,
        after_import_row_id: int,
        *,
        conn: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT
                import_row_id,
                file_path,
                sheet_name,
                row_index,
                business_key,
                source,
                status,
                payload_json
            FROM import_rows
            WHERE import_batch_id = ?
              AND import_row_id > ?
            ORDER BY import_row_id
            LIMIT ?
            """,
            (import_batch_id, after_import_row_id, self.READ_CHUNK_SIZE),
        ).fetchall()
        chunk_rows: list[dict[str, Any]] = []
        for row in rows:
            payload = json_loads(row["payload_json"])
            business_key = self._normalize_text(payload.get("business_key", row["business_key"]))
            source = self._normalize_text(payload.get("source", row["source"]))
            chunk_rows.append(
                {
                    "import_row_id": int(row["import_row_id"]),
                    "file_path": row["file_path"],
                    "sheet_name": row["sheet_name"],
                    "row_index": int(row["row_index"]),
                    "import_status": str(row["status"]),
                    "business_key": business_key,
                    "source": source,
                    "payload": payload,
                }
            )
        return chunk_rows

    def _prime_chunk_cache(
        self,
        chunk_rows: list[dict[str, Any]],
        *,
        project_id: int,
        conn: sqlite3.Connection,
        entries_by_key: dict[str, dict[str, Any]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
        created_entry_keys: set[str],
    ) -> None:
        candidate_keys = sorted(
            {
                row["business_key"]
                for row in chunk_rows
                if row["import_status"] == "ok" and row["business_key"] and row["source"]
            }
        )
        missing_lookup_keys = [key for key in candidate_keys if key not in entries_by_key]
        if missing_lookup_keys:
            existing = self.entries.get_entries_by_keys(missing_lookup_keys, project_id=project_id, conn=conn)
            entries_by_key.update(existing)
            missing_create_keys = [key for key in missing_lookup_keys if key not in existing]
            if missing_create_keys:
                created_entry_keys.update(missing_create_keys)
                entries_by_key.update(
                    self.entries.ensure_entries(
                        missing_create_keys,
                        project_id=project_id,
                        conn=conn,
                    )
                )

        entry_ids_to_load = sorted(
            {
                int(entries_by_key[key]["entry_id"])
                for key in candidate_keys
                if int(entries_by_key[key]["entry_id"]) not in variants_by_entry
                or int(entries_by_key[key]["entry_id"]) not in binding_rows_by_entry
            }
        )
        if not entry_ids_to_load:
            return

        variants = self.catalog.list_variants_for_entries_shallow(entry_ids_to_load, include_trashed=False, conn=conn)
        bindings = self.binding_lookup.list_bindings_for_entries(entry_ids_to_load, conn=conn)
        for entry_id in entry_ids_to_load:
            variants_by_entry[entry_id] = list(variants.get(entry_id, []))
            binding_rows_by_entry[entry_id] = list(bindings.get(entry_id, []))

    def _apply_row_cached(
        self,
        row: dict[str, Any],
        branch_ref: BranchRef,
        *,
        seen_business_keys: set[str],
        entries_by_key: dict[str, dict[str, Any]],
        variants_by_entry: dict[int, list[dict[str, Any]]],
        binding_rows_by_entry: dict[int, list[dict[str, Any]]],
        touched_entry_ids: set[int],
        conn: sqlite3.Connection,
    ) -> str:
        if row["import_status"] != "ok" or not row["business_key"] or not row["source"]:
            return "INVALID_ROW"
        if row["business_key"] in seen_business_keys:
            return "DUPLICATE_KEY_IN_BOOTSTRAP"
        seen_business_keys.add(row["business_key"])

        entry = entries_by_key[row["business_key"]]
        entry_id = int(entry["entry_id"])
        bindings = binding_rows_by_entry.get(entry_id, [])
        variants = variants_by_entry.get(entry_id, [])
        current_binding = self._find_binding(bindings, branch_ref)
        source_variant = self._find_source_variant(entry_id, variants, row["source"])
        if source_variant is not None:
            variant_id = int(source_variant["variant_id"])
            if current_binding is None or int(current_binding["variant_id"]) != variant_id:
                self.bindings.bind(
                    entry_id,
                    branch_ref,
                    variant_id,
                    conn=conn,
                    refresh_orphan_states=False,
                )
                self._upsert_binding_cache(bindings, branch_ref, entry_id, variant_id)
                touched_entry_ids.add(entry_id)
            return "BOUND_EXISTING_VARIANT"

        payload = row["payload"]
        content = self.catalog.build_content(
            payload.get("file_name"),
            row["source"],
            {},
            payload.get("remarks") or {},
        )
        variant_id = self.catalog.create_variant_bare(
            entry_id,
            content["source"],
            file_name=content["file_name"],
            conn=conn,
        )
        if content["remarks"]:
            remark_timestamp = now_iso()
            self.catalog.bulk_upsert_remarks(
                [
                    (variant_id, remark_key, remark_value, remark_timestamp)
                    for remark_key, remark_value in content["remarks"].items()
                ],
                conn=conn,
            )
        self._append_variant_cache(
            variants,
            entry_id,
            variant_id,
            content["file_name"],
            content["source"],
            content["translations"],
            content["remarks"],
        )
        self.bindings.bind(
            entry_id,
            branch_ref,
            variant_id,
            conn=conn,
            refresh_orphan_states=False,
        )
        self._upsert_binding_cache(bindings, branch_ref, entry_id, variant_id)
        touched_entry_ids.add(entry_id)
        return "CREATED_AND_BOUND_VARIANT"

    def _find_source_variant(
        self,
        entry_id: int,
        variants: list[dict[str, Any]],
        source: str,
    ) -> dict[str, Any] | None:
        matches = [variant for variant in variants if variant["source"] == source]
        if not matches:
            return None
        if len(matches) > 1:
            raise RuntimeError(f"duplicate active variants found for entry_id={entry_id}, source={source!r}")
        return matches[0]

    def _append_variant_cache(
        self,
        variants: list[dict[str, Any]],
        entry_id: int,
        variant_id: int,
        file_name: str | None,
        source: str,
        translations: dict[str, Any],
        remarks: dict[str, Any],
    ) -> None:
        content = self.catalog.build_content(file_name, source, translations, remarks)
        variants.append(
            {
                "variant_id": variant_id,
                "entry_id": entry_id,
                "file_name": content["file_name"],
                "source": content["source"],
                "translations": dict(content["translations"]),
                "remarks": dict(content["remarks"]),
                "orphaned_at": None,
                "trashed_at": None,
                "created_at": "",
                "updated_at": "",
            }
        )

    def _upsert_binding_cache(
        self,
        bindings: list[dict[str, Any]],
        branch_ref: BranchRef,
        entry_id: int,
        variant_id: int,
    ) -> None:
        scope_type, scope_value = branch_ref.as_tuple()
        for binding in bindings:
            if binding["scope_type"] == scope_type and binding["scope_value"] == scope_value:
                binding["variant_id"] = variant_id
                return
        bindings.append(
            {
                "scope_type": scope_type,
                "scope_value": scope_value,
                "entry_id": entry_id,
                "variant_id": variant_id,
                "created_at": "",
                "updated_at": "",
            }
        )

    def _find_binding(self, bindings: list[dict[str, Any]], branch_ref: BranchRef) -> dict[str, Any] | None:
        scope_type, scope_value = branch_ref.as_tuple()
        for binding in bindings:
            if binding["scope_type"] == scope_type and binding["scope_value"] == scope_value:
                return binding
        return None

    def _complete_job_in_transaction(
        self,
        job_id: int,
        *,
        summary: dict[str, Any],
        report_path: str,
        conn: sqlite3.Connection,
    ) -> None:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = 'success',
                summary_json = ?,
                report_path = ?,
                artifact_path = NULL,
                finished_at = ?,
                error_message = NULL
            WHERE job_id = ?
            """,
            (
                json_dumps(summary),
                report_path,
                now_iso(),
                job_id,
            ),
        )
        if int(cursor.rowcount or 0) != 1:
            raise KeyError(f"job not found: {job_id}")

    def _validate_summary_extra(self, summary_extra: dict[str, Any] | None) -> dict[str, Any] | None:
        if not summary_extra:
            return None
        unsupported = sorted(set(summary_extra).difference(self.ALLOWED_SUMMARY_EXTRA_KEYS))
        if unsupported:
            joined = ", ".join(unsupported)
            raise ValueError(f"unsupported bootstrap summary_extra key: {joined}")
        return dict(summary_extra)

    def _normalize_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _load_report_rows(self, report_path: str) -> list[dict[str, Any]]:
        payload = json_loads(Path(report_path).read_text(encoding="utf-8"))
        return list(payload.get("rows", []))
