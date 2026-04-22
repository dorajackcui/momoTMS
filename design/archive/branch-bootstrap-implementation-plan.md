# Branch Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 3 branch bootstrap as a dedicated async workflow that creates a new dev branch's initial range from an import batch, reuses existing same-source variants by default, and exposes minimal bootstrap metadata through branch reads.

**Architecture:** Add a dedicated branch bootstrap executor in app/services/branch/bootstrap.py that streams import rows in chunks, resolves `(business_key, source)` against the existing `entry -> live variant` model, and optimizes for bind-heavy reuse hits. Persist minimal bootstrap state on `dev_versions`, expose that state through `BranchCatalogView`, and wire a new `POST /api/projects/{project_id}/branches/bootstrap` route through the existing job-backed workflow layer without folding bootstrap into ordinary branch mutation.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, pytest, openpyxl

**Note:** Git staging and commit steps are intentionally omitted because the user requested manual git operations at the end.

---

## File Structure

**Create**

- app/services/branch/bootstrap.py
  - owns the dedicated bootstrap executor, chunked import-row streaming, duplicate-key detection, row status generation, summary generation, and final branch bootstrap state marking

**Modify**

- `app/db.py`
  - bump schema version and extend `dev_versions` with minimal bootstrap metadata columns
- `app/services/branch/registry.py`
  - add `require_not_bootstrapped` and `mark_bootstrapped`, and return bootstrap metadata in dev-branch reads
- `app/services/read_models/derived/branch_catalog.py`
  - expose bootstrap metadata in `list_dev_branches()`, `get_dev_branch()`, and candidate branch reads
- `app/services/workflows/application.py`
  - wire a new bootstrap workflow into the async job layer and pass `job_id` into streaming workers
- `app/routers/workflows.py`
  - publish `POST /api/projects/{project_id}/branches/bootstrap`
- `app/schemas.py`
  - add `BranchBootstrapRequest` and extend `DevBranchSummary` / `DevBranchDetail` with bootstrap fields
- `tests/test_branch_service.py`
  - add service-level bootstrap regression coverage, including reuse-hit content ignoring, duplicate handling, and chunk-boundary bind-heavy execution
- `tests/test_variant_api.py`
  - add API coverage for the new route, async job contract, bootstrap metadata, and request validation
- `tests/test_services_architecture.py`
  - keep architecture/docs assertions aligned with the new route and active-doc wording
- `docs/system.md`
  - document branch bootstrap state and `dev_versions` metadata additions
- `docs/workflows.md`
  - document bootstrap workflow semantics, statuses, and large-batch behavior
- `docs/contracts.md`
  - document the new route, request shape, summary/report fields, and branch metadata payload additions
- `design/branch-infra-phase-map.md`
  - mark Phase 3 as implemented and point the next session focus to Phase 4

**Keep As-Is But Reference While Editing**

- `app/services/branch/import_batch_mutation.py`
  - use as the streaming/chunked execution reference without merging bootstrap into mutation
- `app/services/imports/service.py`
  - reuse persisted import-batch rows instead of reparsing workbook files
- `app/services/shared/jobs.py`
  - keep report streaming and preview generation behavior aligned with existing async jobs
- `app/services/project/bootstrap.py`
  - rely on `BranchCatalogView` changes so `/state` picks up bootstrap metadata without new wiring

## Assumptions For This Plan

- bootstrap remains limited to `dev/<version>` branches
- bootstrap is allowed when the dev branch does not exist yet or exists with `bootstrap_state = not_bootstrapped`
- a bootstrap job that completes without an unhandled exception marks the branch as `bootstrapped`, even if some rows report `INVALID_ROW` or `DUPLICATE_KEY_IN_BOOTSTRAP`
- bootstrap row statuses stay minimal: `BOUND_EXISTING_VARIANT`, `CREATED_AND_BOUND_VARIANT`, `INVALID_ROW`, and `DUPLICATE_KEY_IN_BOOTSTRAP`
- reuse-hit rows ignore uploaded translations and remarks entirely instead of comparing or filtering them

### Task 1: Lock Service-Level Bootstrap Semantics With Failing Tests

**Files:**
- Modify: `tests/test_branch_service.py`
- Test: `tests/test_branch_service.py`

- [ ] **Step 1: Add failing bootstrap regressions for reuse-hit rows, duplicate keys, and repeated bootstrap rejection**

```python
from app.services.branch.bootstrap import BranchBootstrapService


def test_bootstrap_reuses_existing_variant_and_ignores_uploaded_content(tmp_path) -> None:
    reset_demo()
    services = branch_services()
    bootstrap_service = BranchBootstrapService()

    existing_entry = services.entries.get_or_create_entry("bootstrap.reuse", project_id=1)
    existing_variant_id = services.catalog.create_variant(
        int(existing_entry["entry_id"]),
        services.catalog.build_content(
            "reuse.xlsx",
            "Shared source",
            {"fr": "Authoritative existing"},
            {"context": "existing"},
        ),
    )
    services.bindings.bind_scope(int(existing_entry["entry_id"]), BranchRef.rel_current(), existing_variant_id)

    import_root = tmp_path / "bootstrap-reuse"
    write_import_workbook(
        import_root,
        "bundle/bootstrap.xlsx",
        [
            ["business_key", "source", "fr", "context"],
            ["bootstrap.reuse", "Shared source", "Ignored uploaded text", "ignored"],
            ["bootstrap.create", "Brand new source", "Created from bootstrap", "created"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = bootstrap_service.apply(
        BranchRef.dev("2.4.3"),
        batch["import_batch_id"],
        project_id=1,
        job_id=9001,
    )

    statuses = {row["business_key"]: row["status"] for row in result["report_rows"]}
    assert statuses == {
        "bootstrap.reuse": "BOUND_EXISTING_VARIANT",
        "bootstrap.create": "CREATED_AND_BOUND_VARIANT",
    }
    assert services.catalog.get_variant(existing_variant_id)["translations"]["fr"] == "Authoritative existing"
    assert services.catalog.get_variant(existing_variant_id)["remarks"]["context"] == "existing"
    dev_entries = services.list_branch_entries(BranchRef.dev("2.4.3"))
    assert {item["business_key"] for item in dev_entries} == {"bootstrap.reuse", "bootstrap.create"}
    metadata = BranchRegistryService().get_dev_branch_metadata("2.4.3")
    assert metadata["bootstrap_state"] == "bootstrapped"
    assert metadata["bootstrap_import_batch_id"] == batch["import_batch_id"]
    assert metadata["bootstrap_job_id"] == 9001


def test_bootstrap_reports_duplicate_keys_and_invalid_rows_without_aborting_job(tmp_path) -> None:
    reset_demo()
    bootstrap_service = BranchBootstrapService()

    import_root = tmp_path / "bootstrap-invalid"
    write_import_workbook(
        import_root,
        "bundle/bootstrap.xlsx",
        [
            ["business_key", "source", "fr"],
            ["", "Missing key source", "ignored"],
            ["bootstrap.dup", "First source", "first"],
            ["bootstrap.dup", "Second source", "second"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = bootstrap_service.apply(
        BranchRef.dev("2.4.3"),
        batch["import_batch_id"],
        project_id=1,
        job_id=9002,
    )

    assert [row["status"] for row in result["report_rows"]] == [
        "INVALID_ROW",
        "CREATED_AND_BOUND_VARIANT",
        "DUPLICATE_KEY_IN_BOOTSTRAP",
    ]
    assert result["summary"]["invalid_row_count"] == 1
    assert result["summary"]["duplicate_key_count"] == 1
    assert result["summary"]["created_and_bound_variant_count"] == 1
    assert BranchRegistryService().get_dev_branch_metadata("2.4.3")["bootstrap_state"] == "bootstrapped"


def test_bootstrap_rejects_branch_that_is_already_bootstrapped(tmp_path) -> None:
    reset_demo()
    bootstrap_service = BranchBootstrapService()

    import_root = tmp_path / "bootstrap-repeat"
    write_import_workbook(
        import_root,
        "bundle/bootstrap.xlsx",
        [
            ["business_key", "source", "fr"],
            ["bootstrap.once", "First source", "first"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    first = bootstrap_service.apply(
        BranchRef.dev("2.4.3"),
        batch["import_batch_id"],
        project_id=1,
        job_id=9003,
    )
    assert first["summary"]["processed_count"] == 1

    with pytest.raises(ValueError, match="already bootstrapped"):
        bootstrap_service.apply(
            BranchRef.dev("2.4.3"),
            batch["import_batch_id"],
            project_id=1,
            job_id=9004,
        )
```

- [ ] **Step 2: Add a failing bind-heavy chunk-boundary regression so bootstrap cannot fall back to row-by-row lookup behavior**

```python
def test_bootstrap_processes_bind_heavy_rows_across_chunk_boundary(tmp_path) -> None:
    reset_demo()
    services = branch_services()
    bootstrap_service = BranchBootstrapService()

    workbook_rows: list[list[object]] = [["business_key", "source", "fr"]]
    for index in range(1005):
        business_key = f"bootstrap.chunk.{index}"
        entry = services.entries.get_or_create_entry(business_key, project_id=1)
        variant_id = services.catalog.create_variant(
            int(entry["entry_id"]),
            services.catalog.build_content(
                f"chunk-{index}.xlsx",
                f"Chunk source {index}",
                {"fr": f"Existing {index}"},
                {"context": f"chunk-{index}"},
            ),
        )
        services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.rel_current(), variant_id)
        workbook_rows.append([business_key, f"Chunk source {index}", f"Ignored upload {index}"])

    import_root = tmp_path / "bootstrap-chunk"
    write_import_workbook(import_root, "bundle/chunk.xlsx", workbook_rows)
    batch = ImportService().import_directory(str(import_root))

    result = bootstrap_service.apply(
        BranchRef.dev("2.4.3"),
        batch["import_batch_id"],
        project_id=1,
        job_id=9005,
    )

    assert result["summary"]["processed_count"] == 1005
    assert result["summary"]["bound_existing_variant_count"] == 1005
    assert result["summary"]["created_and_bound_variant_count"] == 0
```

- [ ] **Step 3: Run the new bootstrap service tests and verify they fail before implementation**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k "bootstrap and not api"
```

Expected:

```text
ModuleNotFoundError: No module named 'app.services.branch.bootstrap'
```

### Task 2: Lock API Contract And Branch Metadata With Failing Tests

**Files:**
- Modify: `tests/test_variant_api.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Add failing API regressions for the new route, async job shape, and bootstrap metadata**

```python
def test_branch_bootstrap_api_runs_async_and_exposes_bootstrap_metadata(tmp_path) -> None:
    reset_demo()
    services = branch_services()
    entry = services.entries.get_or_create_entry("api.bootstrap.reuse", project_id=1)
    variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "api-bootstrap.xlsx",
            "API source",
            {"fr": "Existing API text"},
            {"context": "api"},
        ),
    )
    services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.rel_current(), variant_id)

    import_root = tmp_path / "api-bootstrap"
    workbook_path = import_root / "bundle" / "bootstrap.xlsx"
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    workbook_path.write_bytes(
        build_workbook_bytes(
            ["business_key", "source", "fr"],
            [["api.bootstrap.reuse", "API source", "Ignored API text"]],
        )
    )
    batch = ImportService().import_directory(str(import_root))

    with TestClient(app) as client:
        response = client.post(
            "/api/projects/1/branches/bootstrap",
            json={
                "branch_ref": "dev/2.4.3",
                "import_batch_id": batch["import_batch_id"],
            },
        )
        assert response.status_code == 200
        detail = wait_for_job(client, response.json())

        assert detail["job"]["job_type"] == "branch_bootstrap"
        assert detail["job"]["summary"]["input_kind"] == "bootstrap"
        assert detail["job"]["summary"]["bound_existing_variant_count"] == 1
        assert detail["report"]["rows"][0]["status"] == "BOUND_EXISTING_VARIANT"

        branch_detail = client.get("/api/projects/1/branches/dev/2.4.3")
        assert branch_detail.status_code == 200
        payload = branch_detail.json()
        assert payload["bootstrap_state"] == "bootstrapped"
        assert payload["bootstrap_import_batch_id"] == batch["import_batch_id"]
        assert payload["bootstrap_job_id"] == detail["job"]["job_id"]
        assert payload["bootstrapped_at"] is not None

        state_response = client.get("/api/projects/1/state")
        assert state_response.status_code == 200
        state_payload = state_response.json()
        branch_summary = next(item for item in state_payload["dev_branches"] if item["version"] == "2.4.3")
        assert branch_summary["bootstrap_state"] == "bootstrapped"
        assert branch_summary["bootstrap_import_batch_id"] == batch["import_batch_id"]


def test_branch_bootstrap_api_rejects_rel_current() -> None:
    reset_demo()
    sample = DemoService().get_sample("core-cycle")
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    with TestClient(app) as client:
        response = client.post(
            "/api/projects/1/branches/bootstrap",
            json={
                "branch_ref": "rel/current",
                "import_batch_id": batch["import_batch_id"],
            },
        )

    assert response.status_code == 400
    assert "dev" in response.json()["detail"].lower()
```

- [ ] **Step 2: Run the new API tests and verify they fail before route wiring exists**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py -k "branch_bootstrap"
```

Expected:

```text
assert response.status_code == 200
E assert 404 == 200
```

### Task 3: Implement Bootstrap Persistence, Metadata, And The Chunked Executor

**Files:**
- Modify: `app/db.py`
- Modify: `app/services/branch/registry.py`
- Modify: `app/services/read_models/derived/branch_catalog.py`
- Create: app/services/branch/bootstrap.py
- Test: `tests/test_branch_service.py`

- [ ] **Step 1: Extend `dev_versions` so the runtime can distinguish `not_bootstrapped` from `bootstrapped`**

```python
# app/db.py
SCHEMA_VERSION = "variant-v9"

CREATE TABLE dev_versions (
    project_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    version_line TEXT NOT NULL,
    is_candidate_release INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    promoted_at TEXT,
    bootstrapped_at TEXT,
    bootstrap_job_id INTEGER,
    bootstrap_import_batch_id INTEGER,
    PRIMARY KEY (project_id, version),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
```

```python
# app/services/branch/registry.py
def get_dev_branch_metadata(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
    self.projects.require_project(project_id)
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                version,
                version_line,
                is_candidate_release,
                created_at,
                promoted_at,
                bootstrapped_at,
                bootstrap_job_id,
                bootstrap_import_batch_id
            FROM dev_versions
            WHERE project_id = ? AND version = ?
            LIMIT 1
            """,
            (project_id, version),
        ).fetchone()
    if row is None:
        raise KeyError(f"dev branch not found: {version}")
    return {
        "project_id": project_id,
        "version": row["version"],
        "version_series": row["version_line"],
        "is_candidate_release": bool(row["is_candidate_release"]),
        "created_at": row["created_at"],
        "promoted_at": row["promoted_at"],
        "branch_ref": str(self.dev_branch(row["version"])),
        "bootstrap_state": "bootstrapped" if row["bootstrapped_at"] else "not_bootstrapped",
        "bootstrapped_at": row["bootstrapped_at"],
        "bootstrap_job_id": int(row["bootstrap_job_id"]) if row["bootstrap_job_id"] is not None else None,
        "bootstrap_import_batch_id": (
            int(row["bootstrap_import_batch_id"])
            if row["bootstrap_import_batch_id"] is not None
            else None
        ),
    }


def require_not_bootstrapped(
    self,
    version: str,
    project_id: int = DEFAULT_PROJECT_ID,
    conn: sqlite3.Connection | None = None,
) -> None:
    row = (conn or get_conn()).execute(
        """
        SELECT bootstrapped_at
        FROM dev_versions
        WHERE project_id = ? AND version = ?
        LIMIT 1
        """,
        (project_id, version),
    ).fetchone()
    if row and row["bootstrapped_at"] is not None:
        raise ValueError(f"branch already bootstrapped: dev/{version}")


def mark_bootstrapped(
    self,
    version: str,
    *,
    import_batch_id: int,
    job_id: int,
    project_id: int = DEFAULT_PROJECT_ID,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    marker = now_iso()
    if conn is None:
        with get_conn() as local_conn:
            return self.mark_bootstrapped(
                version,
                import_batch_id=import_batch_id,
                job_id=job_id,
                project_id=project_id,
                conn=local_conn,
            )
    updated = conn.execute(
        """
        UPDATE dev_versions
        SET bootstrapped_at = ?,
            bootstrap_job_id = ?,
            bootstrap_import_batch_id = ?
        WHERE project_id = ? AND version = ?
          AND bootstrapped_at IS NULL
        """,
        (marker, job_id, import_batch_id, project_id, version),
    )
    if updated.rowcount != 1:
        raise ValueError(f"branch already bootstrapped: dev/{version}")
    return self.get_dev_branch_metadata(version, project_id)
```

- [ ] **Step 2: Expose bootstrap metadata through branch catalog reads**

```python
# app/services/read_models/derived/branch_catalog.py
query = """
    SELECT
        d.version,
        d.version_line,
        d.is_candidate_release,
        d.created_at,
        d.promoted_at,
        d.bootstrapped_at,
        d.bootstrap_job_id,
        d.bootstrap_import_batch_id,
        COUNT(
            DISTINCT CASE
                WHEN e.entry_id IS NOT NULL AND v.trashed_at IS NULL THEN b.entry_id
                ELSE NULL
            END
        ) AS entry_count
    FROM dev_versions d
    LEFT JOIN scope_bindings b
        ON b.scope_type = 'dev'
       AND b.scope_value = d.version
    LEFT JOIN entries e
        ON e.entry_id = b.entry_id
       AND e.project_id = d.project_id
    LEFT JOIN variants v
        ON v.variant_id = b.variant_id
    WHERE d.project_id = ?
    GROUP BY
        d.project_id,
        d.version,
        d.version_line,
        d.is_candidate_release,
        d.created_at,
        d.promoted_at,
        d.bootstrapped_at,
        d.bootstrap_job_id,
        d.bootstrap_import_batch_id
    ORDER BY d.created_at DESC, d.version DESC
"""
```

```python
{
    "project_id": project_id,
    "version": row["version"],
    "version_series": row["version_line"],
    "branch_ref": str(self.dev_branch(row["version"])),
    "is_candidate_release": bool(row["is_candidate_release"]),
    "entry_count": int(row["entry_count"] or 0),
    "created_at": row["created_at"],
    "promoted_at": row["promoted_at"],
    "bootstrap_state": "bootstrapped" if row["bootstrapped_at"] else "not_bootstrapped",
    "bootstrapped_at": row["bootstrapped_at"],
    "bootstrap_job_id": int(row["bootstrap_job_id"]) if row["bootstrap_job_id"] is not None else None,
    "bootstrap_import_batch_id": (
        int(row["bootstrap_import_batch_id"])
        if row["bootstrap_import_batch_id"] is not None
        else None
    ),
}
```

- [ ] **Step 3: Create `BranchBootstrapService` with chunked import-row loading, duplicate-key detection, and bind-heavy reuse logic**

```python
# app/services/branch/bootstrap.py
from __future__ import annotations

from collections import Counter
from time import perf_counter
import sqlite3
from typing import Any, Generator

from app.db import get_conn, json_loads
from app.services.branch.models import BranchRef
from app.services.branch.registry import BranchRegistryService
from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.variant.bindings import BindingLookupService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.state_coordinator import VariantStateCoordinator


class BranchBootstrapService:
    READ_CHUNK_SIZE = 1000

    def __init__(self) -> None:
        self.imports = ImportService()
        self.projects = ProjectService()
        self.registry = BranchRegistryService()
        self.entries = EntryService()
        self.catalog = VariantCatalogService()
        self.binding_lookup = BindingLookupService()
        self.bindings = VariantStateCoordinator(binding_lookup=self.binding_lookup)

    def apply(
        self,
        branch_ref: BranchRef,
        import_batch_id: int,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
        job_id: int,
    ) -> dict[str, Any]:
        report_rows: list[dict[str, Any]] = []
        row_stream = self.iter_apply(
            branch_ref,
            import_batch_id,
            project_id=project_id,
            job_id=job_id,
        )
        iterator = iter(row_stream)
        while True:
            try:
                report_rows.append(next(iterator))
            except StopIteration as stop:
                summary = dict((stop.value or {}).get("summary", {}))
                break
        return {"summary": summary, "report_rows": report_rows}

    def iter_apply(
        self,
        branch_ref: BranchRef,
        import_batch_id: int,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
        job_id: int,
    ) -> Generator[dict[str, Any], None, dict[str, Any]]:
        if not branch_ref.is_dev:
            raise ValueError("branch bootstrap only supports dev branches")
        self.projects.require_project(project_id)
        self.imports.require_batch_project(import_batch_id, project_id)

        started = perf_counter()
        seen_keys: set[str] = set()
        created_entry_keys: set[str] = set()
        status_counts: Counter[str] = Counter()
        created_variant_count = 0

        with get_conn() as conn:
            self.registry.ensure_dev_branch(branch_ref.branch_value, project_id=project_id, conn=conn)
            self.registry.require_not_bootstrapped(branch_ref.branch_value, project_id=project_id, conn=conn)

            entries_by_key: dict[str, dict[str, Any]] = {}
            variants_by_entry: dict[int, list[dict[str, Any]]] = {}
            binding_rows_by_entry: dict[int, list[dict[str, Any]]] = {}

            processed_count = 0
            last_import_row_id = 0
            while True:
                payload_rows = self._load_chunk(import_batch_id, last_import_row_id, conn=conn)
                if not payload_rows:
                    break
                last_import_row_id = payload_rows[-1]["import_row_id"]
                self._prime_chunk_cache(
                    payload_rows,
                    project_id=project_id,
                    conn=conn,
                    entries_by_key=entries_by_key,
                    variants_by_entry=variants_by_entry,
                    binding_rows_by_entry=binding_rows_by_entry,
                    created_entry_keys=created_entry_keys,
                )
                touched_entry_ids: set[int] = set()
                for row in payload_rows:
                    report_row, created_variant = self._apply_row_cached(
                        row["payload"],
                        branch_ref,
                        seen_keys=seen_keys,
                        entries_by_key=entries_by_key,
                        variants_by_entry=variants_by_entry,
                        binding_rows_by_entry=binding_rows_by_entry,
                        touched_entry_ids=touched_entry_ids,
                        conn=conn,
                    )
                    created_variant_count += int(created_variant)
                    processed_count += 1
                    status_counts.update([report_row["status"]])
                    yield {
                        "business_key": row["payload"].get("business_key"),
                        "file_path": row["file_path"],
                        "sheet_name": row["sheet_name"],
                        "row_index": row["row_index"],
                        "status": report_row["status"],
                    }
                if touched_entry_ids:
                    self.bindings.refresh_orphan_states(list(touched_entry_ids), conn=conn)

            metadata = self.registry.mark_bootstrapped(
                branch_ref.branch_value,
                import_batch_id=import_batch_id,
                job_id=job_id,
                project_id=project_id,
                conn=conn,
            )
            summary = {
                "branch_ref": str(branch_ref),
                "input_kind": "bootstrap",
                "import_batch_id": import_batch_id,
                "processed_count": processed_count,
                "bound_existing_variant_count": status_counts["BOUND_EXISTING_VARIANT"],
                "created_and_bound_variant_count": status_counts["CREATED_AND_BOUND_VARIANT"],
                "invalid_row_count": status_counts["INVALID_ROW"],
                "duplicate_key_count": status_counts["DUPLICATE_KEY_IN_BOOTSTRAP"],
                "created_entry_count": len(created_entry_keys),
                "created_variant_count": created_variant_count,
                "bootstrap_state": metadata["bootstrap_state"],
                "bootstrapped_at": metadata["bootstrapped_at"],
                "bootstrap_job_id": metadata["bootstrap_job_id"],
                "bootstrap_import_batch_id": metadata["bootstrap_import_batch_id"],
                "stages": [
                    {
                        "stage": "branch_bootstrap",
                        "elapsed_ms": int((perf_counter() - started) * 1000),
                        "meta": {
                            "branch_ref": str(branch_ref),
                            "processed_count": processed_count,
                        },
                    }
                ],
            }
            return {"summary": summary}
```

- [ ] **Step 4: Implement row resolution so reuse hits bind existing variants and ignore uploaded content**

```python
def _apply_row_cached(
    self,
    payload: dict[str, Any],
    branch_ref: BranchRef,
    *,
    seen_keys: set[str],
    entries_by_key: dict[str, dict[str, Any]],
    variants_by_entry: dict[int, list[dict[str, Any]]],
    binding_rows_by_entry: dict[int, list[dict[str, Any]]],
    touched_entry_ids: set[int],
    conn: sqlite3.Connection,
) -> tuple[dict[str, Any], bool]:
    business_key = str(payload.get("business_key") or "")
    source = str(payload.get("source") or "")
    if not business_key or not source:
        return {"status": "INVALID_ROW"}, False
    if business_key in seen_keys:
        return {"status": "DUPLICATE_KEY_IN_BOOTSTRAP"}, False
    seen_keys.add(business_key)

    entry = entries_by_key[business_key]
    entry_id = int(entry["entry_id"])
    variants = variants_by_entry.get(entry_id, [])
    bindings = binding_rows_by_entry.get(entry_id, [])
    source_variant = next(
        (variant for variant in variants if variant["source"] == source and variant["trashed_at"] is None),
        None,
    )
    if source_variant is not None:
        variant_id = int(source_variant["variant_id"])
        self.bindings.bind_scope(
            entry_id,
            branch_ref,
            variant_id,
            conn=conn,
            refresh_orphan_states=False,
        )
        self._upsert_binding_cache(bindings, branch_ref, entry_id, variant_id)
        touched_entry_ids.add(entry_id)
        return {"status": "BOUND_EXISTING_VARIANT"}, False

    content = self.catalog.build_content(
        payload.get("file_name"),
        source,
        payload.get("translations", {}),
        payload.get("remarks", {}),
    )
    variant_id = self.catalog.create_variant(entry_id, content, conn=conn)
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
            "trash_until": None,
            "restored_at": None,
            "created_at": "",
            "updated_at": "",
        }
    )
    self.bindings.bind_scope(
        entry_id,
        branch_ref,
        variant_id,
        conn=conn,
        refresh_orphan_states=False,
    )
    self._upsert_binding_cache(bindings, branch_ref, entry_id, variant_id)
    touched_entry_ids.add(entry_id)
    return {"status": "CREATED_AND_BOUND_VARIANT"}, True
```

- [ ] **Step 5: Run the bootstrap service tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k "bootstrap and not api"
```

Expected:

```text
4 passed
```

### Task 4: Wire The Async Workflow Route, Request Models, And API Metadata

**Files:**
- Modify: `app/services/workflows/application.py`
- Modify: `app/routers/workflows.py`
- Modify: `app/schemas.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Add the bootstrap request model and extend branch summary schemas with bootstrap metadata**

```python
# app/schemas.py
class DevBranchSummary(BaseModel):
    project_id: int
    version: str
    version_series: str
    branch_ref: str
    is_candidate_release: bool
    entry_count: int
    created_at: str
    promoted_at: str | None = None
    bootstrap_state: Literal["not_bootstrapped", "bootstrapped"] = "not_bootstrapped"
    bootstrapped_at: str | None = None
    bootstrap_job_id: int | None = None
    bootstrap_import_batch_id: int | None = None


class BranchBootstrapRequest(BaseModel):
    branch_ref: str
    import_batch_id: int
```

- [ ] **Step 2: Teach the workflow layer to run streaming bootstrap jobs and pass `job_id` into the worker**

```python
# app/services/workflows/application.py
from app.services.branch.bootstrap import BranchBootstrapService


class WorkflowApplicationService:
    def __init__(self) -> None:
        self.branch_bootstrap_service = BranchBootstrapService()
        self.branch_mutation_service = BranchMutationService()
        self.branch_replace_service = BranchReplaceService()
        self.fill_service = FillService()
        self.import_service = ImportService()
        self.job_service = JobService()
        self.upload_session_service = UploadSessionService()
        self.qa_scan_service = QaScanService()
        self.trash_restore_service = TrashRestoreService()
        self.pivot_review_service = PivotReviewService()

    def branch_bootstrap(
        self,
        branch_ref: str,
        import_batch_id: int,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        parsed_branch_ref = BranchRef.parse(branch_ref)
        if not parsed_branch_ref.is_dev:
            raise ValueError("branch bootstrap only supports dev branches")
        return self._run_streaming_job_async(
            "branch_bootstrap",
            {
                "branch_ref": branch_ref,
                "import_batch_id": import_batch_id,
                "project_id": project_id,
            },
            lambda job_id: self.branch_bootstrap_service.iter_apply(
                parsed_branch_ref,
                import_batch_id,
                project_id=project_id,
                job_id=job_id,
            ),
            project_id=project_id,
        )

    def _run_streaming_job_async(
        self,
        job_type: str,
        input_payload: dict[str, Any],
        row_stream_factory: Callable[[int], Any],
        project_id: int,
    ) -> dict[str, Any]:
        job_id = self.job_service.create_job(job_type, input_payload, project_id=project_id)

        def run() -> None:
            try:
                self.job_service.complete_job_from_stream(job_id, row_stream_factory(job_id))
            except Exception as exc:
                self.job_service.fail_job(job_id, str(exc))

        submit_background_job(run)
        return self.get_job_detail(job_id, project_id=project_id)
```

- [ ] **Step 3: Publish the route in `app/routers/workflows.py`**

```python
# app/routers/workflows.py
from app.schemas import (
    BranchBootstrapRequest,
    BranchMutationRequest,
    BranchReplacePreview,
    BranchReplaceRequest,
    DevBranchDetail,
    DevBranchSummary,
    FillRequest,
    JobDetail,
    PivotReviewRequest,
    QaRequest,
    ScopedTrashDeleteRequest,
    VariantTrashRestoreRequest,
)


@router.post("/api/projects/{project_id}/branches/bootstrap", response_model=JobDetail)
def project_branch_bootstrap(project_id: int, payload: BranchBootstrapRequest) -> JobDetail:
    service = WorkflowApplicationService()
    return handle_errors(
        lambda: JobDetail(
            **service.branch_bootstrap(
                payload.branch_ref,
                payload.import_batch_id,
                project_id=project_id,
            )
        )
    )
```

- [ ] **Step 4: Run the new bootstrap API tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py -k "branch_bootstrap"
```

Expected:

```text
2 passed
```

### Task 5: Update Docs, Architecture Assertions, And Full Verification

**Files:**
- Modify: `tests/test_services_architecture.py`
- Modify: `docs/system.md`
- Modify: `docs/workflows.md`
- Modify: `docs/contracts.md`
- Modify: `design/branch-infra-phase-map.md`
- Test: `tests/test_branch_service.py`
- Test: `tests/test_variant_api.py`
- Test: `tests/test_services_architecture.py`

- [ ] **Step 1: Update architecture assertions so active docs and route inventory cover bootstrap**

```python
# tests/test_services_architecture.py
def test_active_docs_cover_branch_first_routes_and_replace_rules() -> None:
    contracts_doc = _read_doc("docs/contracts.md")
    workflows_doc = _read_doc("docs/workflows.md")
    system_doc = _read_doc("docs/system.md")

    assert "POST /api/projects/{project_id}/branches/bootstrap" in contracts_doc
    assert "bootstrapped" in contracts_doc
    assert "branch bootstrap" in workflows_doc.lower()
    assert "dev_versions" in system_doc
```

- [ ] **Step 2: Update the active docs and phase map to match the new runtime**

```md
<!-- docs/system.md -->
- `dev_versions` now stores candidate-release metadata plus bootstrap state fields (`bootstrapped_at`, `bootstrap_job_id`, `bootstrap_import_batch_id`) for dev branches
- dev branch metadata can distinguish `not_bootstrapped` from `bootstrapped`
```

```md
<!-- docs/workflows.md -->
- bootstrap is a dedicated async workflow for `dev/<version>` initial range establishment
- bootstrap accepts an import batch with required `business_key + source` and optional partial content columns
- reuse-hit bootstrap rows always report `BOUND_EXISTING_VARIANT` and ignore uploaded content
- bootstrap rejects already bootstrapped branches and reports `INVALID_ROW` or `DUPLICATE_KEY_IN_BOOTSTRAP` for row-local issues
```

```md
<!-- docs/contracts.md -->
- `POST /api/projects/{project_id}/branches/bootstrap` accepts `branch_ref` plus `import_batch_id`
- bootstrap returns async `JobDetail` and reports `BOUND_EXISTING_VARIANT`, `CREATED_AND_BOUND_VARIANT`, `INVALID_ROW`, or `DUPLICATE_KEY_IN_BOOTSTRAP`
- dev branch summary payloads now include `bootstrap_state`, `bootstrapped_at`, `bootstrap_job_id`, and `bootstrap_import_batch_id`
```

```md
<!-- design/branch-infra-phase-map.md -->
### Phase 3: Branch Creation And Bootstrap

Status:

- complete

Artifacts:

- [branch-bootstrap-design.md](../branch-bootstrap-design.md)
- [branch-bootstrap-implementation-plan.md](branch-bootstrap-implementation-plan.md)
```

- [ ] **Step 3: Run the targeted architecture and documentation checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_services_architecture.py
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected:

```text
All architecture tests pass
Documentation validation passed
```

- [ ] **Step 4: Run the end-to-end verification for the whole bootstrap change**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py tests/test_variant_api.py tests/test_services_architecture.py
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected:

```text
Bootstrap service tests, API tests, and architecture tests all pass
Documentation validation passed
```

## Coverage Check

This plan covers every approved requirement in `design/branch-bootstrap-design.md`:

- dedicated bootstrap workflow instead of overloading ordinary mutation
- bootstrap limited to `dev/<version>` and blocked for already bootstrapped branches
- branch initial range defined only by uploaded keys
- operator-facing `business_key + source` row resolution backed by the existing `entry -> variant(source)` model
- reuse-hit rows bind existing variants and ignore uploaded content
- missing same-source rows create new variants and bind them
- no authority content filtering on reuse-hit rows because bootstrap is not an in-place shared-content edit
- minimal branch metadata for `not_bootstrapped` vs `bootstrapped`
- bind-heavy chunked execution for large batches
- row-level statuses and summary counts required by the spec
- async job-backed API contract and updated active docs

It intentionally does not implement:

- Phase 4 range-changing vs content-only mutation taxonomy
- bootstrap preview UX
- branch-to-branch replace or promote redesign
- pivot workflow changes beyond existing behavior
