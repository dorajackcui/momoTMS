# Phase 5 Preview System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the Phase 5 preview family so existing and new workflow previews share one read-only contract, with summary-first large-batch semantics and a common `effect_forecast` meaning for replace, mutation, and bootstrap.

**Architecture:** Introduce the shared preview vocabulary at the schema and service-contract layer first, then adapt existing replace preview and add forecast builders for mutation and bootstrap without reopening Phase 3 or Phase 4 execution semantics. Keep payloads summary-first and row-minimal so the contract scales to `200000` rows.

**Tech Stack:** FastAPI, Pydantic, Python service layer, pytest, Markdown owner docs under `docs/`

---

## File Structure

### Design And Docs

- Modify: `D:\cat\momoTMS\docs\contracts.md`
- Modify: `D:\cat\momoTMS\docs\workflows.md`
- Modify: `D:\cat\momoTMS\design\branch-infra-phase-map.md`

### Shared Preview Contract

- Modify: `D:\cat\momoTMS\app\schemas.py`
- Create or modify: `D:\cat\momoTMS\app\services\branch\preview_contract.py`

### Replace Preview Adoption

- Modify: `D:\cat\momoTMS\app\services\read_models\derived\replace_preview.py`
- Modify: `D:\cat\momoTMS\app\services\branch\replace.py`
- Modify: `D:\cat\momoTMS\app\routers\workflows.py`

### Mutation Preview

- Modify: `D:\cat\momoTMS\app\services\branch\mutation_semantics.py`
- Create or modify: `D:\cat\momoTMS\app\services\branch\mutation_preview.py`
- Modify: `D:\cat\momoTMS\app\routers\workflows.py`

### Bootstrap Preview

- Modify: `D:\cat\momoTMS\app\services\branch\bootstrap.py`
- Create or modify: `D:\cat\momoTMS\app\services\branch\bootstrap_preview.py`
- Modify: `D:\cat\momoTMS\app\routers\workflows.py`

### Tests

- Modify: `D:\cat\momoTMS\tests\test_branch_service.py`
- Modify: `D:\cat\momoTMS\tests\test_variant_api.py`
- Modify: `D:\cat\momoTMS\tests\test_services_architecture.py`

## Task 1: Add The Shared Preview Contract

**Files:**

- Modify: `D:\cat\momoTMS\app\schemas.py`
- Create or modify: `D:\cat\momoTMS\app\services\branch\preview_contract.py`
- Test: `D:\cat\momoTMS\tests\test_branch_service.py`

- [ ] **Step 1: Write the failing unit tests for preview contract helpers**

Add tests that prove the shared helper can build summary counts for:

- `binding_effect`
- `variant_resolution`
- `row_outcome`

Use a fixture-style test input such as:

```python
rows = [
    {"binding_effect": "bind", "variant_resolution": "reuse_existing", "row_outcome": "applied"},
    {"binding_effect": "rebind", "variant_resolution": "reuse_existing", "row_outcome": "applied"},
    {"binding_effect": "none", "variant_resolution": "create_new", "row_outcome": "applied"},
    {"binding_effect": "none", "variant_resolution": "stay_current", "row_outcome": "noop"},
    {"binding_effect": "none", "variant_resolution": "stay_current", "row_outcome": "missing"},
]
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k preview_contract
```

Expected:

- fail because the helper or vocabulary does not exist yet

- [ ] **Step 3: Add the shared preview vocabulary and summary builder**

Implement a focused helper module such as:

```python
PREVIEW_KIND_VALUES = ("input_precheck", "effect_forecast")
EFFECT_BINDING_VALUES = ("none", "bind", "rebind")
EFFECT_VARIANT_VALUES = ("stay_current", "reuse_existing", "create_new")
EFFECT_OUTCOME_VALUES = ("applied", "noop", "missing", "invalid")
```

and a summary helper that returns:

```python
{
    "binding_effect_counts": {...},
    "variant_resolution_counts": {...},
    "row_outcome_counts": {...},
}
```

- [ ] **Step 4: Add or update Pydantic response models**

Add response models that can represent:

- the common preview envelope
- replace preview as an `effect_forecast`
- future mutation and bootstrap preview payloads without forcing full row uniformity

Keep rows minimal and avoid content-heavy nested payloads.

- [ ] **Step 5: Run the focused test again**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k preview_contract
```

Expected:

- PASS

## Task 2: Migrate Replace Preview To The Shared Family

**Files:**

- Modify: `D:\cat\momoTMS\app\services\read_models\derived\replace_preview.py`
- Modify: `D:\cat\momoTMS\app\services\branch\replace.py`
- Modify: `D:\cat\momoTMS\app\schemas.py`
- Test: `D:\cat\momoTMS\tests\test_branch_service.py`
- Test: `D:\cat\momoTMS\tests\test_variant_api.py`

- [ ] **Step 1: Extend the service test with Phase 5 replace preview expectations**

Add assertions for each replace preview row:

```python
assert row["binding_effect"] in {"none", "bind", "rebind"}
assert row["variant_resolution"] in {"stay_current", "reuse_existing"}
assert row["row_outcome"] in {"applied", "noop"}
```

and summary assertions such as:

```python
assert preview["summary"]["variant_resolution_counts"]["reuse_existing_count"] >= 1
assert preview["summary"]["binding_effect_counts"]["rebind_count"] >= 1
```

- [ ] **Step 2: Run the replace-focused tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k replace_preview
```

Expected:

- fail because replace preview rows do not expose the new shared semantic block

- [ ] **Step 3: Update `ReplacePreviewView` to emit the preview envelope**

Return:

```python
{
    "preview_kind": "effect_forecast",
    "workflow_kind": "branch_replace",
    "request_echo": {
        "source_branch_ref": str(source_branch_ref),
        "target_branch_ref": str(target_branch_ref),
    },
    "summary": {...},
    "rows": [...],
}
```

Map row statuses as follows:

```python
"ADD_TO_TARGET" -> ("bind", "reuse_existing", "applied")
"REBIND_TARGET" -> ("rebind", "reuse_existing", "applied")
"KEEP_IN_TARGET" -> ("none", "stay_current", "noop")
"REMOVE_FROM_TARGET" -> (None, None, "applied")
```

For `REMOVE_FROM_TARGET`, keep the workflow-specific `status` and omit any invented generic field that would distort meaning.

- [ ] **Step 4: Update the public schema and router response**

Keep the route stable:

```python
@router.post("/api/projects/{project_id}/branches/replace/preview", ...)
```

but return the new envelope and the new summary block instead of the old top-level count-only shape.

- [ ] **Step 5: Run service and API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k replace_preview tests/test_variant_api.py -k replace_preview
```

Expected:

- PASS

## Task 3: Add Mutation Preview Without Reopening Execute Semantics

**Files:**

- Modify: `D:\cat\momoTMS\app\services\branch\mutation_semantics.py`
- Create or modify: `D:\cat\momoTMS\app\services\branch\mutation_preview.py`
- Modify: `D:\cat\momoTMS\app\routers\workflows.py`
- Test: `D:\cat\momoTMS\tests\test_branch_service.py`
- Test: `D:\cat\momoTMS\tests\test_variant_api.py`

- [ ] **Step 1: Write failing tests for mutation preview semantics**

Add focused test inputs that cover:

- content update on current target
- same-entry rebind to an existing variant
- create-and-bind new variant
- missing-target content mutation
- invalid row

Assert that preview rows expose:

```python
assert row["binding_effect"] in {"none", "bind", "rebind"}
assert row["variant_resolution"] in {"stay_current", "reuse_existing", "create_new"}
assert row["row_outcome"] in {"applied", "noop", "missing", "invalid"}
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k mutation_preview
```

Expected:

- fail because no mutation preview builder or route exists yet

- [ ] **Step 3: Build a dedicated mutation preview adapter**

Create a preview builder that reuses Phase 4 decision logic but stops short of execution.

The builder should return rows like:

```python
{
    "business_key": "phase4.content.update",
    "status": "UPDATED_BOUND_VARIANT",
    "binding_effect": "none",
    "variant_resolution": "stay_current",
    "row_outcome": "applied",
}
```

and summary counts that answer:

- reuse existing
- create new
- stay current
- bind or rebind
- applied, noop, missing, invalid

- [ ] **Step 4: Expose a dedicated mutation preview route**

Add a preview route alongside execute, for example:

```python
POST /api/projects/{project_id}/branches/mutations/preview
```

Keep the existing execute route unchanged.

- [ ] **Step 5: Run service and API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k mutation_preview tests/test_variant_api.py -k mutation_preview
```

Expected:

- PASS

## Task 4: Add Bootstrap Effect Preview

**Files:**

- Modify: `D:\cat\momoTMS\app\services\branch\bootstrap.py`
- Create or modify: `D:\cat\momoTMS\app\services\branch\bootstrap_preview.py`
- Modify: `D:\cat\momoTMS\app\routers\workflows.py`
- Test: `D:\cat\momoTMS\tests\test_branch_service.py`
- Test: `D:\cat\momoTMS\tests\test_variant_api.py`

- [ ] **Step 1: Write failing tests for bootstrap preview**

Cover:

- existing same-source reuse
- create-and-bind new variant
- invalid row
- duplicate business key inside bootstrap batch

Assert representative rows such as:

```python
assert row["status"] == "BOUND_EXISTING_VARIANT"
assert row["binding_effect"] == "bind"
assert row["variant_resolution"] == "reuse_existing"
assert row["row_outcome"] == "applied"
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k bootstrap_preview
```

Expected:

- fail because bootstrap preview does not exist yet

- [ ] **Step 3: Add a bootstrap preview service that mirrors bootstrap resolution without writes**

Implement a read-only builder that:

- loads import rows in chunks
- resolves same-source reuse versus create-new forecast
- classifies invalid and duplicate rows
- emits only row identity plus the shared semantic block

Return rows like:

```python
{
    "business_key": row["business_key"],
    "file_path": row["file_path"],
    "sheet_name": row["sheet_name"],
    "row_index": row["row_index"],
    "status": "CREATED_AND_BOUND_VARIANT",
    "binding_effect": "bind",
    "variant_resolution": "create_new",
    "row_outcome": "applied",
}
```

- [ ] **Step 4: Expose a dedicated bootstrap preview route**

Add a route such as:

```python
POST /api/projects/{project_id}/branches/bootstrap/preview
```

This route must be read-only and must not create a job.

- [ ] **Step 5: Run service and API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k bootstrap_preview tests/test_variant_api.py -k bootstrap_preview
```

Expected:

- PASS

## Task 5: Update Active Docs And Architecture Assertions

**Files:**

- Modify: `D:\cat\momoTMS\docs\contracts.md`
- Modify: `D:\cat\momoTMS\docs\workflows.md`
- Modify: `D:\cat\momoTMS\design\branch-infra-phase-map.md`
- Test: `D:\cat\momoTMS\tests\test_services_architecture.py`

- [ ] **Step 1: Write or update docs assertions first**

Add expectations that active docs mention:

- `preview_kind`
- `input_precheck`
- `effect_forecast`
- `variant_resolution`
- read-only preview behavior
- preview routes for replace, mutation, and bootstrap after implementation

- [ ] **Step 2: Run the architecture and docs assertions to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_services_architecture.py
```

Expected:

- fail because the docs do not yet describe the Phase 5 preview family

- [ ] **Step 3: Update owner docs and phase map**

Update:

- `docs/workflows.md` with preview family language, read-only rules, and workflow mappings
- `docs/contracts.md` with preview envelope and route contracts
- `design/branch-infra-phase-map.md` to mark Phase 5 as designed and implementation-ready

- [ ] **Step 4: Run docs assertions again**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_services_architecture.py
```

Expected:

- PASS

## Task 6: Run Focused Verification And Docs Validation

**Files:**

- Modify if needed: `D:\cat\momoTMS\tests\test_branch_service.py`
- Modify if needed: `D:\cat\momoTMS\tests\test_variant_api.py`
- Modify if needed: `D:\cat\momoTMS\tests\test_services_architecture.py`

- [ ] **Step 1: Run focused branch service coverage**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py
```

Expected:

- PASS

- [ ] **Step 2: Run focused API coverage**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py
```

Expected:

- PASS

- [ ] **Step 3: Run architecture and docs assertions**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_services_architecture.py
```

Expected:

- PASS

- [ ] **Step 4: Run docs validation**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected:

- PASS

## Self-Review Checklist

- [ ] Spec coverage: each design requirement maps to at least one task above
- [ ] Placeholder scan: no placeholder markers or empty implementation instructions remain
- [ ] Type consistency: `preview_kind`, `workflow_kind`, `binding_effect`, `variant_resolution`, and `row_outcome` stay consistent across all tasks

## Handoff

This implementation plan is intentionally saved under `design/` because the current session requested both plan and spec in that folder and requested no git operations.

If execution starts later, choose one of two modes:

1. Subagent-Driven
2. Inline Execution
