# Phase 4 Mutation Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical semantic layer for branch mutation rows and summaries while preserving the current public mutation statuses and legacy request shape.

**Architecture:** Introduce one shared `mutation_semantics` module under `app/services/branch/` and make both `DirectMutationApplier` and `ImportBatchMutationApplier` emit the same additive semantic fields on every row plus the same semantic summary counters. Keep `direct` and `import_batch` as compatibility transports, keep existing status values and legacy summary counters intact, and update active docs to describe the new row and summary contract without changing routes.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, pytest

**Note:** Git staging and commit steps are intentionally omitted because the user requested no git operations in this round.

---

## File Structure

**Create**

- `app/services/branch/mutation_semantics.py`
  - owns the canonical Phase 4 semantic vocabulary, row field helpers, and summary counter builder shared by direct and import-batch mutation

**Modify**

- `app/services/branch/direct_mutation.py`
  - annotate direct mutation rows with semantic fields and add semantic summary counts without changing legacy statuses
- `app/services/branch/import_batch_mutation.py`
  - annotate import-batch rows with the same semantic fields and add the same semantic summary counts
- `tests/test_branch_service.py`
  - lock row-level and summary-level Phase 4 semantics for both direct and import-batch mutation paths
- `tests/test_variant_api.py`
  - verify the additive semantics survive the `/branches/mutations` API surface for both request-scoped and job-backed mutation execution
- `tests/test_services_architecture.py`
  - keep active docs assertions aligned with the new mutation contract wording
- `docs/workflows.md`
  - document the canonical mutation classes, row semantics, summary semantics, and compatibility rules
- `docs/contracts.md`
  - document the additive mutation row fields and semantic summary counters published through the workflow API
- `design/branch-infra-phase-map.md`
  - mark Phase 4 as implemented and point future sessions at Phase 5

**Keep As-Is But Reference While Editing**

- `app/services/branch/mutations.py`
  - keep the runtime dispatcher unchanged unless a small import wiring change becomes necessary
- `app/services/branch/policy.py`
  - preserve current `direct` and `import_batch` validation; input-kind cleanup is deferred to Phase 9
- `app/services/workflows/application.py`
  - reuse the existing request-scoped versus streaming job orchestration as-is
- `app/routers/workflows.py`
  - reuse the existing route surface because Phase 4 is additive to report payloads, not a route redesign
- `app/schemas.py`
  - keep `BranchMutationRequest` unchanged because the mutation report payloads already flow through `dict[str, Any]`

## Assumptions For This Plan

- Phase 4 remains additive: existing row `status` values stay public and unchanged
- `direct` and `import_batch` remain accepted request forms during implementation, even though they are no longer the semantic center of the design
- mutation rows gain four additive semantic fields only:
  - `mutation_class`
  - `binding_effect`
  - `content_effect`
  - `row_outcome`
- mutation summaries gain four additive grouped counters only:
  - `mutation_class_counts`
  - `binding_effect_counts`
  - `content_effect_counts`
  - `row_outcome_counts`
- semantic summary counts are derived from the new semantic fields only, never inferred from legacy summary counters
- the current `content_filtered_by_authority` row flag and `content_filtered_by_authority_count` summary counter stay intact
- no mutation route paths, request bodies, or branch catalog payloads change in Phase 4

### Task 1: Lock Direct-Mutation Semantics With Failing Service Tests

**Files:**
- Modify: `tests/test_branch_service.py`
- Test: `tests/test_branch_service.py`

- [ ] **Step 1: Add a failing direct-mutation regression that proves a content-only update gets the Phase 4 semantic fields**

```python
def test_direct_content_update_emits_phase4_semantics() -> None:
    reset_demo()
    mutation_service = BranchMutationService()

    result = mutation_service.apply(
        BranchRef.rel_current(),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "common.welcome",
                    "translations_by_lang": {"fr": "Bonjour Phase 4"},
                    "remarks_by_key": {"context": "phase4-direct"},
                }
            ],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "UPDATED_BOUND_VARIANT"
    assert row["mutation_class"] == "content"
    assert row["binding_effect"] == "none"
    assert row["content_effect"] == "update"
    assert row["row_outcome"] == "applied"

    summary = result["summary"]
    assert summary["updated_bound_variant_count"] == 1
    assert summary["mutation_class_counts"] == {"range_count": 0, "content_count": 1}
    assert summary["binding_effect_counts"] == {
        "none_count": 1,
        "bind_count": 0,
        "rebind_count": 0,
    }
    assert summary["content_effect_counts"] == {
        "none_count": 0,
        "create_count": 0,
        "update_count": 1,
        "filtered_count": 0,
    }
    assert summary["row_outcome_counts"] == {
        "applied_count": 1,
        "noop_count": 0,
        "missing_count": 0,
    }
```

- [ ] **Step 2: Add failing direct-mutation regressions for missing-target content mutation, range-create, and filtered rebind**

```python
def test_direct_content_mutation_missing_target_emits_missing_semantics() -> None:
    reset_demo()
    mutation_service = BranchMutationService()

    result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "phase4.missing.content",
                    "translations_by_lang": {"fr": "Missing target"},
                }
            ],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "MISSING_IN_SCOPE"
    assert row["mutation_class"] == "content"
    assert row["binding_effect"] == "none"
    assert row["content_effect"] == "none"
    assert row["row_outcome"] == "missing"
    assert result["summary"]["row_outcome_counts"]["missing_count"] == 1


def test_direct_range_create_emits_bind_and_create_semantics() -> None:
    reset_demo()
    mutation_service = BranchMutationService()

    result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "phase4.range.create",
                    "source": "Phase 4 source",
                    "translations_by_lang": {"fr": "Created by direct"},
                    "remarks_by_key": {"context": "phase4"},
                    "file_name": "phase4.xlsx",
                }
            ],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "CREATED_AND_BOUND_VARIANT"
    assert row["mutation_class"] == "range"
    assert row["binding_effect"] == "bind"
    assert row["content_effect"] == "create"
    assert row["row_outcome"] == "applied"


def test_direct_filtered_rebind_emits_range_rebind_filtered_semantics() -> None:
    reset_demo()
    services = branch_services()
    mutation_service = BranchMutationService()

    entry = services.entries.get_or_create_entry("phase4.filtered.rebind", project_id=1)
    current_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "phase4-current.xlsx",
            "Current source",
            {"fr": "Current text"},
            {"context": "current"},
        ),
    )
    target_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "phase4-target.xlsx",
            "Target source",
            {"fr": "Target text"},
            {"context": "target"},
        ),
    )
    services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.5.1"), current_variant_id)
    services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.2"), target_variant_id)

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "phase4.filtered.rebind",
                    "source": "Target source",
                    "translations_by_lang": {"fr": "Filtered content"},
                    "remarks_by_key": {"context": "Filtered remark"},
                }
            ],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert row["content_filtered_by_authority"] is True
    assert row["mutation_class"] == "range"
    assert row["binding_effect"] == "rebind"
    assert row["content_effect"] == "filtered"
    assert row["row_outcome"] == "applied"
    assert result["summary"]["content_effect_counts"]["filtered_count"] == 1
    assert result["summary"]["binding_effect_counts"]["rebind_count"] == 1
```

- [ ] **Step 3: Run the direct-mutation semantic tests and verify they fail before implementation**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_branch_service.py::test_direct_content_update_emits_phase4_semantics `
  tests/test_branch_service.py::test_direct_content_mutation_missing_target_emits_missing_semantics `
  tests/test_branch_service.py::test_direct_range_create_emits_bind_and_create_semantics `
  tests/test_branch_service.py::test_direct_filtered_rebind_emits_range_rebind_filtered_semantics
```

Expected:

```text
KeyError: 'mutation_class'
```

### Task 2: Lock Import-Batch Parity And API Payload Semantics With Failing Tests

**Files:**
- Modify: `tests/test_branch_service.py`
- Modify: `tests/test_variant_api.py`
- Test: `tests/test_branch_service.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Add failing import-batch regressions that prove the same business scenarios emit the same semantic layer**

```python
def test_import_batch_content_update_emits_phase4_semantics(tmp_path) -> None:
    reset_demo()
    mutation_service = BranchMutationService()

    create_result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "phase4.import.update",
                    "source": "Phase 4 import source",
                    "translations_by_lang": {"fr": "Initial import text"},
                    "remarks_by_key": {"context": "initial"},
                    "file_name": "phase4-import.xlsx",
                }
            ],
        },
    )
    assert create_result["report_rows"][0]["status"] == "CREATED_AND_BOUND_VARIANT"

    import_root = tmp_path / "phase4-import-update"
    write_import_workbook(
        import_root,
        "bundle/phase4-import.xlsx",
        [
            ["business_key", "source", "fr", "context"],
            ["phase4.import.update", "Phase 4 import source", "Updated import text", "updated"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
            "mark_as_candidate_release": True,
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "UPDATED_BOUND_VARIANT"
    assert row["mutation_class"] == "content"
    assert row["binding_effect"] == "none"
    assert row["content_effect"] == "update"
    assert row["row_outcome"] == "applied"


def test_import_batch_filtered_rebind_emits_phase4_semantics(tmp_path) -> None:
    reset_demo()
    services = branch_services()
    mutation_service = BranchMutationService()

    entry = services.entries.get_or_create_entry("phase4.import.filtered", project_id=1)
    actor_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "actor.xlsx",
            "Actor source",
            {"fr": "Actor content"},
            {"context": "actor"},
        ),
    )
    target_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "target.xlsx",
            "Target source",
            {"fr": "Target owner"},
            {"context": "target"},
        ),
    )
    services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.5.1"), actor_variant_id)
    services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.2"), target_variant_id)

    import_root = tmp_path / "phase4-import-filtered"
    write_import_workbook(
        import_root,
        "bundle/phase4-import-filtered.xlsx",
        [
            ["business_key", "source", "fr", "context"],
            ["phase4.import.filtered", "Target source", "Filtered import", "filtered"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
            "mark_as_candidate_release": True,
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert row["content_filtered_by_authority"] is True
    assert row["mutation_class"] == "range"
    assert row["binding_effect"] == "rebind"
    assert row["content_effect"] == "filtered"
    assert row["row_outcome"] == "applied"
```

- [ ] **Step 2: Add failing API regressions for both direct and streaming mutation responses**

```python
def test_branch_mutation_api_direct_reports_phase4_semantics() -> None:
    reset_demo()

    with TestClient(app) as client:
        response = client.post(
            "/api/projects/1/branches/mutations",
            json={
                "branch_ref": "rel/current",
                "input": {
                    "kind": "direct",
                    "changes": [
                        {
                            "business_key": "common.welcome",
                            "translations_by_lang": {"fr": "Bonjour API Phase 4"},
                        }
                    ],
                },
            },
        )

    assert response.status_code == 200
    detail = response.json()
    row = detail["report"]["rows"][0]
    assert row["mutation_class"] == "content"
    assert row["binding_effect"] == "none"
    assert row["content_effect"] == "update"
    assert row["row_outcome"] == "applied"
    assert detail["job"]["summary"]["mutation_class_counts"]["content_count"] == 1


def test_branch_mutation_api_import_batch_reports_phase4_semantics(tmp_path) -> None:
    reset_demo()
    create_bound_variant(
        project_id=1,
        business_key="phase4.api.import",
        source="Phase 4 API source",
        translations={"fr": "Initial API content"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )

    import_root = tmp_path / "phase4-api-import"
    workbook_path = import_root / "bundle" / "phase4-api-import.xlsx"
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    workbook_path.write_bytes(
        build_workbook_bytes(
            ["business_key", "source", "fr", "context"],
            [["phase4.api.import", "Phase 4 API source", "Phase 4 import text", "phase4"]],
        )
    )
    batch = ImportService().import_directory(str(import_root))

    with TestClient(app) as client:
        response = client.post(
            "/api/projects/1/branches/mutations",
            json={
                "branch_ref": "dev/2.4.3",
                "input": {
                    "kind": "import_batch",
                    "import_batch_id": batch["import_batch_id"],
                    "mark_as_candidate_release": True,
                },
            },
        )
        assert response.status_code == 200
        detail = wait_for_job(client, response.json())

    row = detail["report"]["rows"][0]
    assert row["mutation_class"] in {"range", "content"}
    assert "binding_effect" in row
    assert "content_effect" in row
    assert "row_outcome" in row
    assert "mutation_class_counts" in detail["job"]["summary"]
    assert "binding_effect_counts" in detail["job"]["summary"]
    assert "content_effect_counts" in detail["job"]["summary"]
    assert "row_outcome_counts" in detail["job"]["summary"]
```

- [ ] **Step 3: Run the import-batch and API semantic tests and verify they fail before implementation**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_branch_service.py::test_import_batch_content_update_emits_phase4_semantics `
  tests/test_branch_service.py::test_import_batch_filtered_rebind_emits_phase4_semantics
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_variant_api.py::test_branch_mutation_api_direct_reports_phase4_semantics `
  tests/test_variant_api.py::test_branch_mutation_api_import_batch_reports_phase4_semantics
```

Expected:

```text
AssertionError: 'mutation_class' not in row
```

### Task 3: Introduce The Shared Mutation-Semantics Module

**Files:**
- Create: `app/services/branch/mutation_semantics.py`
- Test: `tests/test_branch_service.py`

- [ ] **Step 1: Create the canonical Phase 4 semantic vocabulary and row helper**

```python
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal


MutationClass = Literal["range", "content"]
BindingEffect = Literal["none", "bind", "rebind"]
ContentEffect = Literal["none", "create", "update", "filtered"]
RowOutcome = Literal["applied", "noop", "missing"]


@dataclass(frozen=True)
class MutationSemantics:
    mutation_class: MutationClass
    binding_effect: BindingEffect
    content_effect: ContentEffect
    row_outcome: RowOutcome

    def as_dict(self) -> dict[str, str]:
        return {
            "mutation_class": self.mutation_class,
            "binding_effect": self.binding_effect,
            "content_effect": self.content_effect,
            "row_outcome": self.row_outcome,
        }


def semantics_row(
    base: dict[str, object],
    *,
    mutation_class: MutationClass,
    binding_effect: BindingEffect,
    content_effect: ContentEffect,
    row_outcome: RowOutcome,
) -> dict[str, object]:
    row = dict(base)
    row.update(
        MutationSemantics(
            mutation_class=mutation_class,
            binding_effect=binding_effect,
            content_effect=content_effect,
            row_outcome=row_outcome,
        ).as_dict()
    )
    return row
```

- [ ] **Step 2: Add a shared semantic summary builder so both appliers count the same way**

```python
@dataclass
class MutationSemanticSummaryBuilder:
    mutation_class_counts: Counter[str]
    binding_effect_counts: Counter[str]
    content_effect_counts: Counter[str]
    row_outcome_counts: Counter[str]

    def __init__(self) -> None:
        self.mutation_class_counts = Counter()
        self.binding_effect_counts = Counter()
        self.content_effect_counts = Counter()
        self.row_outcome_counts = Counter()

    def add_row(self, row: dict[str, object]) -> None:
        self.mutation_class_counts[str(row["mutation_class"])] += 1
        self.binding_effect_counts[str(row["binding_effect"])] += 1
        self.content_effect_counts[str(row["content_effect"])] += 1
        self.row_outcome_counts[str(row["row_outcome"])] += 1

    def as_dict(self) -> dict[str, dict[str, int]]:
        return {
            "mutation_class_counts": {
                "range_count": self.mutation_class_counts["range"],
                "content_count": self.mutation_class_counts["content"],
            },
            "binding_effect_counts": {
                "none_count": self.binding_effect_counts["none"],
                "bind_count": self.binding_effect_counts["bind"],
                "rebind_count": self.binding_effect_counts["rebind"],
            },
            "content_effect_counts": {
                "none_count": self.content_effect_counts["none"],
                "create_count": self.content_effect_counts["create"],
                "update_count": self.content_effect_counts["update"],
                "filtered_count": self.content_effect_counts["filtered"],
            },
            "row_outcome_counts": {
                "applied_count": self.row_outcome_counts["applied"],
                "noop_count": self.row_outcome_counts["noop"],
                "missing_count": self.row_outcome_counts["missing"],
            },
        }
```

- [ ] **Step 3: Run the direct semantic tests again to verify the helper module imports cleanly but the appliers still need integration**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_branch_service.py::test_direct_content_update_emits_phase4_semantics `
  tests/test_branch_service.py::test_direct_content_mutation_missing_target_emits_missing_semantics `
  tests/test_branch_service.py::test_direct_range_create_emits_bind_and_create_semantics `
  tests/test_branch_service.py::test_direct_filtered_rebind_emits_range_rebind_filtered_semantics
```

Expected:

```text
Failures still come from missing semantic fields on direct rows, not from import errors in mutation_semantics.py
```

### Task 4: Refactor `DirectMutationApplier` To Emit Phase 4 Row And Summary Semantics

**Files:**
- Modify: `app/services/branch/direct_mutation.py`
- Test: `tests/test_branch_service.py`

- [ ] **Step 1: Import the shared helper and collect semantic summary counts during `apply()`**

```python
from app.services.branch.mutation_semantics import (
    MutationSemanticSummaryBuilder,
    semantics_row,
)


def apply(
    self,
    branch_ref: BranchRef,
    changes: list[dict[str, Any]],
    policy: BranchMutationPolicy,
    project_id: int,
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    started = perf_counter()
    status_counts: Counter[str] = Counter()
    semantic_counts = MutationSemanticSummaryBuilder()
    report_rows: list[dict[str, Any]] = []
    created_entry_count = 0
    filtered_count = 0
    for change in changes:
        row = self.apply_change(branch_ref, change, policy, project_id, conn=conn)
        created_entry_count += int(row.pop("created_entry", False))
        status_counts.update([str(row["status"])])
        filtered_count += int(bool(row.get("content_filtered_by_authority")))
        semantic_counts.add_row(row)
        report_rows.append(row)
    summary = {
        "branch_ref": str(branch_ref),
        "input_kind": "direct",
        "processed_count": len(report_rows),
        "created_entry_count": created_entry_count,
        **self._status_summary(status_counts, filtered_count=filtered_count),
        **semantic_counts.as_dict(),
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
```

- [ ] **Step 2: Replace raw row literals in `apply_change()` with explicit semantic rows**

```python
if entry is None:
    return semantics_row(
        {
            "business_key": business_key,
            "branch_ref": str(branch_ref),
            "status": "MISSING_IN_SCOPE",
            "created_entry": created_entry,
        },
        mutation_class="content" if change.get("source") is None else "range",
        binding_effect="none",
        content_effect="none",
        row_outcome="missing",
    )

if change.get("source") is None and self.resolution.variant_matches(current_variant, merged):
    return semantics_row(
        {
            "business_key": business_key,
            "branch_ref": str(branch_ref),
            "variant_id": int(current_variant["variant_id"]),
            "status": "NOOP",
            "created_entry": created_entry,
        },
        mutation_class="content",
        binding_effect="none",
        content_effect="none",
        row_outcome="noop",
    )

if decision.filtered:
    return semantics_row(
        {
            "business_key": business_key,
            "branch_ref": str(branch_ref),
            "variant_id": int(current_variant["variant_id"]),
            "status": "NOOP",
            "content_filtered_by_authority": True,
            "created_entry": created_entry,
        },
        mutation_class="content",
        binding_effect="none",
        content_effect="filtered",
        row_outcome="noop",
    )

return semantics_row(
    {
        "business_key": business_key,
        "branch_ref": str(branch_ref),
        "variant_id": int(current_variant["variant_id"]),
        "status": "UPDATED_BOUND_VARIANT",
        "created_entry": created_entry,
    },
    mutation_class="content",
    binding_effect="none",
    content_effect="update",
    row_outcome="applied",
)
```

- [ ] **Step 3: Encode range-mutation semantics explicitly for create, bind, rebind, update, and filtered-rebind paths**

```python
had_current_binding = current_binding is not None

if target_variant is None:
    variant_id = self.catalog.create_variant(entry_id, merged, conn=conn)
    self.bindings.bind_scope(entry_id, branch_ref, variant_id, conn=conn)
    return semantics_row(
        {
            "business_key": business_key,
            "branch_ref": str(branch_ref),
            "variant_id": variant_id,
            "status": "CREATED_AND_BOUND_VARIANT",
            "created_entry": created_entry,
        },
        mutation_class="range",
        binding_effect="rebind" if had_current_binding else "bind",
        content_effect="create",
        row_outcome="applied",
    )

if decision.filtered and not current_matches_target:
    self.bindings.bind_scope(entry_id, branch_ref, target_variant_id, conn=conn)
    return semantics_row(
        {
            "business_key": business_key,
            "branch_ref": str(branch_ref),
            "variant_id": target_variant_id,
            "status": "BOUND_EXISTING_VARIANT",
            "content_filtered_by_authority": True,
            "created_entry": created_entry,
        },
        mutation_class="range",
        binding_effect="rebind" if had_current_binding else "bind",
        content_effect="filtered",
        row_outcome="applied",
    )

if payload_matches_target:
    self.bindings.bind_scope(entry_id, branch_ref, target_variant_id, conn=conn)
    return semantics_row(
        {
            "business_key": business_key,
            "branch_ref": str(branch_ref),
            "variant_id": target_variant_id,
            "status": "BOUND_EXISTING_VARIANT",
            "created_entry": created_entry,
        },
        mutation_class="range",
        binding_effect="rebind" if had_current_binding else "bind",
        content_effect="none",
        row_outcome="applied",
    )

return semantics_row(
    {
        "business_key": business_key,
        "branch_ref": str(branch_ref),
        "variant_id": target_variant_id,
        "status": "UPDATED_AND_BOUND_EXISTING_VARIANT" if not current_matches_target else "UPDATED_BOUND_VARIANT",
        "created_entry": created_entry,
    },
    mutation_class="range" if not current_matches_target else "content",
    binding_effect="rebind" if not current_matches_target else "none",
    content_effect="update",
    row_outcome="applied",
)
```

- [ ] **Step 4: Run the direct semantic service tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_branch_service.py::test_direct_content_update_emits_phase4_semantics `
  tests/test_branch_service.py::test_direct_content_mutation_missing_target_emits_missing_semantics `
  tests/test_branch_service.py::test_direct_range_create_emits_bind_and_create_semantics `
  tests/test_branch_service.py::test_direct_filtered_rebind_emits_range_rebind_filtered_semantics
```

Expected:

```text
All direct Phase 4 semantic tests pass
```

### Task 5: Refactor `ImportBatchMutationApplier` To Reuse The Same Semantics

**Files:**
- Modify: `app/services/branch/import_batch_mutation.py`
- Test: `tests/test_branch_service.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Mirror the direct summary integration so import-batch jobs publish the same grouped semantic counts**

```python
from app.services.branch.mutation_semantics import (
    MutationSemanticSummaryBuilder,
    semantics_row,
)


semantic_counts = MutationSemanticSummaryBuilder()
...
status = self._apply_row_cached(...)
status_counts.update([str(status["status"])])
filtered_count += int(bool(status.get("content_filtered_by_authority")))
semantic_counts.add_row(status)
...
summary = {
    "branch_ref": str(branch_ref),
    "input_kind": "import_batch",
    "import_batch_id": import_batch_id,
    "mark_as_candidate_release": mark_as_candidate_release,
    "version_series": version_series,
    "processed_count": processed_count,
    "created_entry_count": len(created_entry_keys),
    **self._status_summary(status_counts, filtered_count=filtered_count),
    **semantic_counts.as_dict(),
    "stages": [
        {
            "stage": "apply_scope_mutation",
            "elapsed_ms": int((perf_counter() - started) * 1000),
            "meta": {
                "branch_ref": str(branch_ref),
                "input_kind": "import_batch",
                "processed_count": processed_count,
            },
        }
    ],
}
```

- [ ] **Step 2: Replace status-only dictionaries in `_apply_row_cached()` with semantic rows that match the direct path**

```python
if current_variant is not None and requested_source == current_variant["source"]:
    if self.resolution.variant_matches(current_variant, merged):
        return semantics_row(
            {"status": "NOOP"},
            mutation_class="content",
            binding_effect="none",
            content_effect="none",
            row_outcome="noop",
        )
    if decision.filtered:
        return semantics_row(
            {
                "status": "NOOP",
                "content_filtered_by_authority": True,
            },
            mutation_class="content",
            binding_effect="none",
            content_effect="filtered",
            row_outcome="noop",
        )
    ...
    return semantics_row(
        {"status": "UPDATED_BOUND_VARIANT"},
        mutation_class="content",
        binding_effect="none",
        content_effect="update",
        row_outcome="applied",
    )

if source_variant is None:
    ...
    return semantics_row(
        {"status": "CREATED_AND_BOUND_VARIANT"},
        mutation_class="range",
        binding_effect="rebind" if current_binding is not None else "bind",
        content_effect="create",
        row_outcome="applied",
    )

if self.resolution.variant_matches(source_variant, merged) and not current_matches:
    ...
    return semantics_row(
        {"status": "BOUND_EXISTING_VARIANT"},
        mutation_class="range",
        binding_effect="rebind" if current_binding is not None else "bind",
        content_effect="none",
        row_outcome="applied",
    )
```

- [ ] **Step 3: Run the import-batch semantic tests and API tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_branch_service.py::test_import_batch_content_update_emits_phase4_semantics `
  tests/test_branch_service.py::test_import_batch_filtered_rebind_emits_phase4_semantics
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_variant_api.py::test_branch_mutation_api_direct_reports_phase4_semantics `
  tests/test_variant_api.py::test_branch_mutation_api_import_batch_reports_phase4_semantics
```

Expected:

```text
All import-batch and API Phase 4 semantic tests pass
```

### Task 6: Update Active Docs, Architecture Assertions, And Full Verification

**Files:**
- Modify: `tests/test_services_architecture.py`
- Modify: `docs/workflows.md`
- Modify: `docs/contracts.md`
- Modify: `design/branch-infra-phase-map.md`
- Test: `tests/test_services_architecture.py`
- Test: `tests/test_branch_service.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Extend the architecture doc assertions to require the new Phase 4 terminology**

```python
def test_active_docs_cover_branch_first_routes_and_replace_rules() -> None:
    contracts_doc = _read_doc("docs/contracts.md")
    workflows_doc = _read_doc("docs/workflows.md")

    assert "mutation_class" in contracts_doc
    assert "binding_effect" in contracts_doc
    assert "content_effect" in contracts_doc
    assert "row_outcome" in contracts_doc
    assert "mutation_class_counts" in contracts_doc
    assert "range mutation" in workflows_doc
    assert "content mutation" in workflows_doc
    assert "content mutation must never implicitly change branch range" in workflows_doc
    assert "legacy input shapes" in workflows_doc
```

- [ ] **Step 2: Update the owner docs and roadmap to reflect the live Phase 4 contract**

```md
<!-- docs/workflows.md -->
- branch mutation now exposes two canonical mutation classes: `range mutation` and `content mutation`
- `direct` and `import_batch` remain runtime transports, not top-level mutation semantics
- every mutation report row now adds `mutation_class`, `binding_effect`, `content_effect`, and `row_outcome`
- every mutation summary now adds grouped semantic counters under `mutation_class_counts`, `binding_effect_counts`, `content_effect_counts`, and `row_outcome_counts`
- content mutation never silently upgrades into range mutation; missing-target content work reports `MISSING_IN_SCOPE` plus `row_outcome = missing`
```

```md
<!-- docs/contracts.md -->
- `POST /api/projects/{project_id}/branches/mutations` remains the route for both direct and import-batch mutation
- mutation report rows keep legacy `status` and may also include `content_filtered_by_authority = true`
- mutation report rows now also include `mutation_class`, `binding_effect`, `content_effect`, and `row_outcome`
- mutation summaries keep legacy counters and also publish `mutation_class_counts`, `binding_effect_counts`, `content_effect_counts`, and `row_outcome_counts`
```

```md
<!-- design/branch-infra-phase-map.md -->
### Phase 4: Mutation Contract

Status:

- complete

Artifacts:

- [phase-4-mutation-contract-design.md](phase-4-mutation-contract-design.md)
- [phase-4-mutation-contract-implementation-plan.md](phase-4-mutation-contract-implementation-plan.md)

Session focus:

- Phase 4 semantic convergence is implemented; next move to Phase 5 preview convergence
```

- [ ] **Step 3: Run the architecture and docs checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_services_architecture.py
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected:

```text
Architecture tests pass
Documentation validation passed
```

- [ ] **Step 4: Run the end-to-end verification for the full Phase 4 change**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py tests/test_variant_api.py tests/test_services_architecture.py
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected:

```text
Phase 4 mutation service tests, API tests, and architecture tests all pass
Documentation validation passed
```

## Coverage Check

This plan covers every approved requirement in `design/phase-4-mutation-contract-design.md`:

- one canonical branch mutation model with two top-level classes: `range` and `content`
- branch-neutral semantics shared by `rel/current` and `dev/<version>`
- additive row fields for `mutation_class`, `binding_effect`, `content_effect`, and `row_outcome`
- additive grouped summary counters derived from the semantic layer only
- preservation of existing public `status` values and legacy status counters
- preservation of `content_filtered_by_authority` and filtered-count compatibility behavior
- explicit missing-target semantics for content mutation without silently degrading into range mutation
- direct and import-batch parity through one shared semantic helper
- deferred treatment of legacy `direct` and `import_batch` naming rather than public API redesign
- active docs and roadmap updates aligned with the implemented runtime contract

It intentionally does not implement:

- Phase 5 preview convergence
- replace or promote semantic redesign
- pivot preview work
- lifecycle closure work
- removal of `direct` and `import_batch` from the public request contract
