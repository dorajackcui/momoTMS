# Branch Authority Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Phase 2 authority model so lower-authority branches can still reuse or rebind existing variants while their unauthorized `translations + remarks` edits are filtered instead of hard-failing.

**Architecture:** Keep the existing target-variant resolution flow in `app/services/branch/`, but replace the current hard-stop authority checks with a shared content-authority decision that is evaluated after target resolution. Preserve existing public bind or update statuses where possible, and add explicit mutation metadata plus summary counts so the runtime can distinguish true no-op rows from authority-filtered content edits.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite-backed services, pytest, openpyxl

---

## File Structure

**Modify**

- `app/services/branch/policy.py`
  - add a reusable content-authority decision helper that distinguishes `allowed` from `filtered`
- `app/services/branch/direct_mutation.py`
  - apply authority filtering after resolved-target selection and preserve legal bind or rebind work
- `app/services/branch/import_batch_mutation.py`
  - mirror the direct-mutation filtering semantics in chunked import application
- `tests/test_branch_service.py`
  - add direct and import-batch regression coverage for filtered-content reuse, source-switch rebind, and orphan editing
- `tests/test_variant_api.py`
  - add API coverage for the new summary count and row metadata on branch mutation responses
- `docs/workflows.md`
  - update the owner doc for mutation semantics
- `docs/contracts.md`
  - document the new mutation response metadata because the route payload shape changes

**Keep As-Is But Reference While Editing**

- `app/services/branch/variant_resolution.py`
  - keep target-resolution behavior unchanged; use it as the pre-authority boundary
- `app/services/branch/mutations.py`
  - verify summary shapes still pass through untouched after service changes
- `app/routers/workflows.py`
  - confirm route response models still accept the updated job detail payload

## Assumption For This Plan

This plan assumes the public row `status` values for branch mutation stay as close as possible to the current enums:

- keep `NOOP`, `BOUND_EXISTING_VARIANT`, `UPDATED_BOUND_VARIANT`, `UPDATED_AND_BOUND_EXISTING_VARIANT`, and `CREATED_AND_BOUND_VARIANT`
- add `content_filtered_by_authority: true` to row payloads only when a requested content edit was dropped
- add `content_filtered_by_authority_count` to mutation summaries

That preserves the Phase 2 internal distinction without forcing a larger route-contract rewrite in the same change.

### Task 1: Lock The New Direct-Mutation Semantics With Failing Tests

**Files:**
- Modify: `tests/test_branch_service.py`
- Test: `tests/test_branch_service.py`

- [ ] **Step 1: Write the failing direct-mutation regressions**

```python
def test_lower_authority_same_variant_edit_is_filtered_but_binding_is_kept() -> None:
    reset_demo()
    service = branch_services()
    mutation_service = BranchMutationService()

    entry = service.entries.get_or_create_entry("authority.shared.current", project_id=1)
    variant_id = service.catalog.create_variant(
        int(entry["entry_id"]),
        service.catalog.build_content(
            "authority.xlsx",
            "Shared source",
            {"fr": "Shared owner"},
            {"context": "owner"},
        ),
    )
    service.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.2"), variant_id)
    service.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.5.1"), variant_id)

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "authority.shared.current",
                    "translations_by_lang": {"fr": "Should be filtered"},
                }
            ],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "NOOP"
    assert row["content_filtered_by_authority"] is True
    assert result["summary"]["content_filtered_by_authority_count"] == 1
    assert service.catalog.get_variant(variant_id)["translations"]["fr"] == "Shared owner"


def test_lower_authority_source_switch_rebinds_existing_target_and_filters_content() -> None:
    reset_demo()
    service = branch_services()
    mutation_service = BranchMutationService()
    inspection = EntryTimelineDataset()

    entry = service.entries.get_or_create_entry("authority.rebind.filtered", project_id=1)
    actor_variant_id = service.catalog.create_variant(
        int(entry["entry_id"]),
        service.catalog.build_content(
            "actor.xlsx",
            "Actor source",
            {"fr": "Actor content"},
            {"context": "actor"},
        ),
    )
    target_variant_id = service.catalog.create_variant(
        int(entry["entry_id"]),
        service.catalog.build_content(
            "target.xlsx",
            "Target source",
            {"fr": "Target owner"},
            {"context": "target"},
        ),
    )
    service.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.5.1"), actor_variant_id)
    service.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.2"), target_variant_id)

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "authority.rebind.filtered",
                    "source": "Target source",
                    "translations_by_lang": {"fr": "Filtered patch"},
                    "remarks_by_key": {"context": "filtered"},
                }
            ],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert row["content_filtered_by_authority"] is True
    rebound_variant = next(
        item
        for item in inspection.get("authority.rebind.filtered")["variants"]
        if item["variant_id"] == target_variant_id
    )
    assert rebound_variant["translations"]["fr"] == "Target owner"
    assert rebound_variant["remarks"]["context"] == "target"


def test_orphan_variant_can_be_rebound_and_edited_in_one_row() -> None:
    reset_demo()
    service = branch_services()
    mutation_service = BranchMutationService()

    entry = service.entries.get_or_create_entry("authority.orphan", project_id=1)
    variant_id = service.catalog.create_variant(
        int(entry["entry_id"]),
        service.catalog.build_content(
            "orphan.xlsx",
            "Shared source",
            {"fr": "Before orphan"},
            {"context": "before"},
        ),
    )
    service.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.2"), variant_id)
    service.bindings.remove_binding(int(entry["entry_id"]), BranchRef.dev("2.4.2"))

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "authority.orphan",
                    "source": "Shared source",
                    "translations_by_lang": {"fr": "After orphan"},
                    "remarks_by_key": {"context": "after"},
                }
            ],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "UPDATED_AND_BOUND_EXISTING_VARIANT"
    assert "content_filtered_by_authority" not in row
    variant = service.catalog.get_variant(variant_id)
    assert variant["translations"]["fr"] == "After orphan"
    assert variant["remarks"]["context"] == "after"
```

- [ ] **Step 2: Run the new direct-mutation tests and verify they fail against the current hard-stop logic**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k "authority and (shared_current or rebind_filtered or orphan)"
```

Expected:

```text
FAIL ... expected content_filtered_by_authority metadata or filtered rebind behavior, but current code still returns FORBIDDEN_BY_AUTHORITY
```

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_branch_service.py
git commit -m "test: lock direct mutation authority filtering behavior"
```

### Task 2: Implement Shared Authority Decisions And Direct-Mutation Filtering

**Files:**
- Modify: `app/services/branch/policy.py`
- Modify: `app/services/branch/direct_mutation.py`
- Test: `tests/test_branch_service.py`

- [ ] **Step 1: Add a reusable content-authority decision helper in `app/services/branch/policy.py`**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ContentAuthorityDecision:
    content_changed: bool
    allowed: bool
    filtered: bool


class AuthorityPolicy:
    @classmethod
    def evaluate_content_edit(
        cls,
        actor_branch_ref: BranchRef,
        bound_branch_refs: list[BranchRef],
        *,
        content_changed: bool,
    ) -> ContentAuthorityDecision:
        if not content_changed:
            return ContentAuthorityDecision(content_changed=False, allowed=False, filtered=False)
        if not bound_branch_refs:
            return ContentAuthorityDecision(content_changed=True, allowed=True, filtered=False)
        allowed = cls.can_mutate_variant(actor_branch_ref, bound_branch_refs)
        return ContentAuthorityDecision(
            content_changed=True,
            allowed=allowed,
            filtered=not allowed,
        )
```

- [ ] **Step 2: Replace hard-stop `FORBIDDEN_BY_AUTHORITY` branches in `app/services/branch/direct_mutation.py`**

```python
decision = AuthorityPolicy.evaluate_content_edit(
    branch_ref,
    bound_branch_refs,
    content_changed=not self.resolution.variant_matches(target_variant, merged),
)

row: dict[str, Any] = {
    "business_key": business_key,
    "branch_ref": str(branch_ref),
    "variant_id": target_variant_id,
    "created_entry": created_entry,
}

if decision.filtered:
    if not current_matches_target:
        self.bindings.bind_scope(entry_id, branch_ref, target_variant_id, conn=conn)
        row["status"] = "BOUND_EXISTING_VARIANT"
    else:
        row["status"] = "NOOP"
    row["content_filtered_by_authority"] = True
    return row
```

- [ ] **Step 3: Update direct-mutation summary counting so filtered rows are not miscounted as hard forbids**

```python
def _status_summary(self, status_counts: Counter[str], *, filtered_count: int) -> dict[str, int]:
    return {
        "updated_bound_variant_count": status_counts["UPDATED_BOUND_VARIANT"],
        "bound_existing_variant_count": status_counts["BOUND_EXISTING_VARIANT"],
        "updated_and_bound_existing_variant_count": status_counts["UPDATED_AND_BOUND_EXISTING_VARIANT"],
        "created_and_bound_variant_count": status_counts["CREATED_AND_BOUND_VARIANT"],
        "missing_in_scope_count": status_counts["MISSING_IN_SCOPE"],
        "noop_count": status_counts["NOOP"],
        "forbidden_by_authority_count": status_counts["FORBIDDEN_BY_AUTHORITY"],
        "content_filtered_by_authority_count": filtered_count,
    }
```

- [ ] **Step 4: Run the focused direct-mutation tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k "authority and (shared_current or rebind_filtered or orphan)"
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit the direct-mutation implementation**

```bash
git add app/services/branch/policy.py app/services/branch/direct_mutation.py tests/test_branch_service.py
git commit -m "feat: filter unauthorized direct mutation content edits"
```

### Task 3: Lock Import-Batch And API Reporting Semantics With Failing Tests

**Files:**
- Modify: `tests/test_branch_service.py`
- Modify: `tests/test_variant_api.py`
- Test: `tests/test_branch_service.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Add import-batch and API regressions for filtered-content reporting**

```python
def test_lower_authority_import_batch_rebinds_existing_target_and_filters_content(tmp_path) -> None:
    reset_demo()
    service = branch_services()
    entry = service.entries.get_or_create_entry("authority.import.filtered", project_id=1)
    owner_variant_id = service.catalog.create_variant(
        int(entry["entry_id"]),
        service.catalog.build_content(
            "owner.xlsx",
            "Target source",
            {"fr": "Owner content"},
            {"context": "owner"},
        ),
    )
    actor_variant_id = service.catalog.create_variant(
        int(entry["entry_id"]),
        service.catalog.build_content(
            "actor.xlsx",
            "Actor source",
            {"fr": "Actor content"},
            {"context": "actor"},
        ),
    )
    service.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.2"), owner_variant_id)
    service.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.5.1"), actor_variant_id)

    import_root = tmp_path / "authority-import-filtered"
    write_import_workbook(
        import_root,
        "bundle/authority.xlsx",
        [
            ["business_key", "source", "fr", "context"],
            ["authority.import.filtered", "Target source", "Filtered import", "filtered"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = BranchMutationService().apply(
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
    assert result["summary"]["content_filtered_by_authority_count"] == 1
    assert service.catalog.get_variant(owner_variant_id)["translations"]["fr"] == "Owner content"


def test_branch_mutation_api_reports_filtered_content_without_hard_failure() -> None:
    reset_demo()
    services = branch_services()
    entry = services.entries.get_or_create_entry("authority.api.filtered", project_id=1)
    variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "authority.xlsx",
            "Shared source",
            {"fr": "Owner content"},
            {"context": "owner"},
        ),
    )
    services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.2"), variant_id)
    services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.5.1"), variant_id)

    with TestClient(app) as client:
        response = client.post(
            "/api/projects/1/branches/mutations",
            json={
                "branch_ref": "dev/2.5.1",
                "input": {
                    "kind": "direct",
                    "changes": [
                        {
                            "business_key": "authority.api.filtered",
                            "translations_by_lang": {"fr": "Filtered by API"},
                        }
                    ],
                },
            },
        )

    assert response.status_code == 200
    detail = response.json()
    assert detail["job"]["summary"]["content_filtered_by_authority_count"] == 1
    assert detail["report"]["rows"][0]["status"] == "NOOP"
    assert detail["report"]["rows"][0]["content_filtered_by_authority"] is True
```

- [ ] **Step 2: Run the new import and API tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k "authority and import_filtered"
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py -k "authority and api and filtered"
```

Expected:

```text
FAIL ... expected content_filtered_by_authority metadata/count, but current code still reports FORBIDDEN_BY_AUTHORITY
```

- [ ] **Step 3: Commit the failing import and API tests**

```bash
git add tests/test_branch_service.py tests/test_variant_api.py
git commit -m "test: lock import and API authority filter reporting"
```

### Task 4: Implement Import-Batch Filtering And Mutation Report Metadata

**Files:**
- Modify: `app/services/branch/import_batch_mutation.py`
- Modify: `app/services/branch/direct_mutation.py`
- Modify: `tests/test_branch_service.py`
- Modify: `tests/test_variant_api.py`
- Test: `tests/test_branch_service.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Mirror the direct-mutation filtering path inside `app/services/branch/import_batch_mutation.py`**

```python
decision = AuthorityPolicy.evaluate_content_edit(
    target_branch,
    bound_branch_refs,
    content_changed=not self.resolution.variant_matches(source_variant, merged),
)

if decision.filtered:
    if not current_matches:
        self.bindings.bind_scope(
            entry_id,
            target_branch,
            variant_id,
            conn=conn,
            refresh_orphan_states=False,
        )
        self._upsert_binding_cache(bindings, target_branch, entry_id, variant_id)
        touched_entry_ids.add(entry_id)
        return {
            "status": "BOUND_EXISTING_VARIANT",
            "content_filtered_by_authority": True,
        }
    return {
        "status": "NOOP",
        "content_filtered_by_authority": True,
    }
```

- [ ] **Step 2: Normalize row construction so both direct and import paths expose the same filtered metadata**

```python
row = {
    "business_key": payload["business_key"],
    "file_path": row["file_path"],
    "sheet_name": row["sheet_name"],
    "row_index": row["row_index"],
    "status": result["status"],
}
if result.get("content_filtered_by_authority"):
    row["content_filtered_by_authority"] = True
```

- [ ] **Step 3: Update mutation summaries to count filtered rows separately from true forbids**

```python
filtered_count = 0
for row in report_rows:
    if row.get("content_filtered_by_authority"):
        filtered_count += 1

summary = {
    ...
    "content_filtered_by_authority_count": filtered_count,
}
```

- [ ] **Step 4: Run the focused service and API suites and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py -k "authority"
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py -k "authority or branches/mutations"
```

Expected:

```text
PASS for the new filtered-authority scenarios and no regressions in existing mutation route tests
```

- [ ] **Step 5: Commit the import-batch and reporting implementation**

```bash
git add app/services/branch/import_batch_mutation.py app/services/branch/direct_mutation.py tests/test_branch_service.py tests/test_variant_api.py
git commit -m "feat: preserve rebinding when authority filters content edits"
```

### Task 5: Update Docs And Run End-To-End Verification

**Files:**
- Modify: `docs/workflows.md`
- Modify: `docs/contracts.md`
- Modify: `design/branch-authority-model.md`
- Test: `tests/test_branch_service.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Update the workflow owner doc to match the new authority behavior**

```md
- lower-authority content-change attempts no longer hard-fail by default
- after target variant resolution, unauthorized `translations + remarks` edits are filtered while otherwise legal bind or rebind work still proceeds
- mutation summaries report `content_filtered_by_authority_count`
- mutation rows may include `content_filtered_by_authority = true` when the requested content edit was dropped
```

- [ ] **Step 2: Update `docs/contracts.md` to describe the added mutation response metadata**

```md
- `POST /api/projects/{project_id}/branches/mutations` may return mutation report rows with `content_filtered_by_authority = true` when a requested content edit is dropped after authority evaluation
- branch mutation summaries may include `content_filtered_by_authority_count`
- row `status` still describes the applied bind or update effect; the authority-filtered flag explains whether requested content edits were omitted
```

- [ ] **Step 3: Keep the Phase 2 design note aligned with the implementation naming**

```md
- note that the first implementation exposes the internal authority-filtered distinction as row metadata plus a summary count
- keep replace or promote and pivot review explicitly deferred
```

- [ ] **Step 4: Run the full verification for this change type**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py tests/test_variant_api.py
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected:

```text
All targeted pytest cases pass
Documentation validation passed
```

- [ ] **Step 5: Commit the docs and verification follow-through**

```bash
git add docs/workflows.md docs/contracts.md design/branch-authority-model.md design/branch-authority-implementation-plan.md
git commit -m "docs: align branch authority workflow semantics"
```

## Coverage Check

This plan covers every requirement in [design/branch-authority-model.md](branch-authority-model.md):

- authority protects only `translations + remarks`
- `source` change is handled by target resolution first
- authority is evaluated against the resolved target variant
- lower-authority content edits are filtered rather than auto-forked
- legal bind or rebind work is preserved
- orphan variants with no current bindings remain editable when rebound
- internal filtered-content semantics are preserved through explicit runtime metadata

It intentionally does not implement:

- replace or promote semantics
- pivot review semantics
- broader mutation taxonomy cleanup beyond what Phase 2 needs
