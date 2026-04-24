# Phase 6 Branch-To-Branch Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify `branch_replace` into a pure target-binding rewrite, remove candidate or promote metadata entirely, and align backend, frontend, tests, and docs with the new Phase 6 model.

**Architecture:** Keep the existing `branch_replace` route family but strip it down to one workflow: compare source and target bindings for preview, then rewrite only the target bindings inside one transaction during execute. Remove candidate and promote state from `dev_versions`, branch request or response models, `/state`, frontend defaults, and tests so the runtime treats branches only as binding-view collections plus bootstrap facts.

**Tech Stack:** FastAPI, Pydantic, SQLite, React 19, TypeScript, TanStack Query, pytest, Playwright, PowerShell

---

This plan intentionally omits git commands because the current phase guidance is to avoid git operations while executing the cleanup.

### Task 1: Remove Candidate Or Promote Metadata From Backend Contracts

**Files:**
- Modify: `app/db.py`
- Modify: `app/schemas.py`
- Modify: `app/services/read_models/types.py`
- Modify: `app/services/read_models/repository.py`
- Modify: `app/services/read_models/derived/branch_catalog.py`
- Modify: `app/services/read_models/derived/branch_summary.py`
- Modify: `app/services/project/bootstrap.py`
- Test: `tests/test_variant_api.py`
- Test: `tests/test_variant_refactor_services.py`

- [ ] **Step 1: Write the failing backend contract tests**

```python
def test_project_state_omits_candidate_release_metadata() -> None:
    reset_demo()
    sample = DemoService().get_sample("core-cycle")
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    with TestClient(app) as client:
        mutation = client.post(
            "/api/projects/1/branches/mutations",
            json={
                "branch_ref": f"dev/{sample['dev_version']}",
                "input": {
                    "kind": "import_batch",
                    "import_batch_id": batch["import_batch_id"],
                },
            },
        )
        assert mutation.status_code == 200
        wait_for_job(client, mutation.json())
        state_payload = client.get("/api/projects/1/state").json()

    assert "candidate_dev_branch" not in state_payload
    assert all("is_candidate_release" not in item for item in state_payload["dev_branches"])
    assert all("promoted_at" not in item for item in state_payload["dev_branches"])


def test_branch_summary_items_omit_candidate_release_metadata() -> None:
    reset_demo()
    summary = BranchSummaryView().build(project_id=1, lang="fr")
    assert all("is_candidate_release" not in item for item in summary["branches"])
```

- [ ] **Step 2: Run the focused backend tests and verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py::test_project_state_omits_candidate_release_metadata tests/test_variant_refactor_services.py::test_branch_summary_query_budget_with_active_dev_branch`

Expected: FAIL because `/state`, branch summaries, and typed branch payloads still expose candidate or promote fields.

- [ ] **Step 3: Remove the fields from the DB-backed branch model and response schemas**

```python
# app/db.py
CREATE TABLE dev_versions (
    project_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    version_line TEXT NOT NULL,
    created_at TEXT NOT NULL,
    bootstrapped_at TEXT,
    bootstrap_job_id INTEGER,
    bootstrap_import_batch_id INTEGER,
    PRIMARY KEY (project_id, version),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);


# app/schemas.py
class DevBranchSummary(BaseModel):
    project_id: int
    version: str
    version_series: str
    branch_ref: str
    entry_count: int
    bootstrap_state: Literal["not_bootstrapped", "bootstrapped"] = "not_bootstrapped"
    bootstrapped_at: str | None = None
    bootstrap_job_id: int | None = None
    bootstrap_import_batch_id: int | None = None
    created_at: str


class ProductStateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project: ProjectSummary
    project_schema: ProjectSchemaSummary = Field(alias="schema")
    release_summary: dict[str, Any] = Field(default_factory=dict)
    dev_branches: list[DevBranchSummary] = Field(default_factory=list)
    imports: list[ImportBatchSummary] = Field(default_factory=list)
    jobs: list[JobSummary] = Field(default_factory=list)
```

```python
# app/services/project/bootstrap.py
return {
    "project": project,
    "schema": self.project_service.get_schema(project_id),
    "release_summary": self.branch_catalog.release_summary(project_id, skip_project_check=True),
    "dev_branches": dev_branches,
    "imports": self.import_service.list_batches(project_id=project_id),
    "jobs": self.job_service.list_jobs(project_id=project_id),
}
```

```python
# app/services/read_models/derived/branch_catalog.py
query = """
    SELECT
        d.version,
        d.version_line,
        d.created_at,
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
    ...
"""
```

- [ ] **Step 4: Run the focused backend tests again**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py::test_project_state_omits_candidate_release_metadata tests/test_variant_refactor_services.py::test_branch_summary_query_budget_with_active_dev_branch`

Expected: PASS with `/state` exposing only `release_summary`, `dev_branches`, `imports`, and `jobs`, and branch summaries no longer exposing candidate metadata.

### Task 2: Remove Candidate Input From Branch Mutation And Branch Registry

**Files:**
- Modify: `app/schemas.py`
- Modify: `app/services/branch/mutations.py`
- Modify: `app/services/branch/import_batch_mutation.py`
- Modify: `app/services/branch/registry.py`
- Test: `tests/test_branch_service.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Write the failing mutation-input and summary tests**

```python
def test_import_batch_mutation_no_longer_accepts_candidate_flag() -> None:
    payload = {
        "branch_ref": "dev/2.4.3",
        "input": {
            "kind": "import_batch",
            "import_batch_id": 1,
            "mark_as_candidate_release": True,
        },
    }
    with TestClient(app) as client:
        response = client.post("/api/projects/1/branches/mutations", json=payload)
    assert response.status_code == 422


def test_import_batch_mutation_summary_omits_candidate_metadata() -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])
    result = BranchMutationService().apply(
        BranchRef.dev(sample["dev_version"]),
        {"kind": "import_batch", "import_batch_id": batch["import_batch_id"]},
    )
    assert "mark_as_candidate_release" not in result["summary"]
```

- [ ] **Step 2: Run the focused mutation tests and verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py::test_import_batch_mutation_summary_omits_candidate_metadata tests/test_variant_api.py::test_scope_routes_and_removed_compatibility_surface`

Expected: FAIL because mutation input still accepts `mark_as_candidate_release` and import-batch summaries still report candidate metadata.

- [ ] **Step 3: Remove the flag from request models and mutation orchestration**

```python
# app/schemas.py
class BranchImportBatchMutationInput(BaseModel):
    kind: Literal["import_batch"]
    import_batch_id: int
```

```python
# app/services/branch/mutations.py
if branch_ref.is_dev:
    dev_branch = self.branch_registry.ensure_dev_branch(
        branch_ref.branch_value,
        project_id,
        conn=conn,
    )

return self.import_batch.apply(
    branch_ref,
    int(input_payload["import_batch_id"]),
    project_id,
    conn=conn,
    version_series=(dev_branch or {}).get("version_series"),
)
```

```python
# app/services/branch/import_batch_mutation.py
def apply(
    self,
    branch_ref: BranchRef,
    import_batch_id: int,
    project_id: int,
    conn: sqlite3.Connection,
    version_series: str | None = None,
) -> dict[str, Any]:
    ...
    summary = {
        "branch_ref": str(branch_ref),
        "input_kind": "import_batch",
        "import_batch_id": import_batch_id,
        "version_series": version_series,
        "processed_count": processed_count,
        ...
    }
```

```python
# app/services/branch/registry.py
def ensure_dev_branch(
    self,
    version: str,
    project_id: int = DEFAULT_PROJECT_ID,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    version_series = derive_version_series(version)
    ...
    conn.execute(
        """
        INSERT INTO dev_versions(
            project_id,
            version,
            version_line,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (project_id, version, version_series, now_iso()),
    )
```

- [ ] **Step 4: Re-run the focused mutation tests**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py::test_import_batch_mutation_summary_omits_candidate_metadata tests/test_variant_api.py::test_scope_routes_and_removed_compatibility_surface`

Expected: PASS with `mark_as_candidate_release` rejected at validation time and mutation summaries omitting candidate metadata.

### Task 3: Rewrite Branch Replace As Pure Target-Binding Rewrite

**Files:**
- Modify: `app/services/branch/policy.py`
- Modify: `app/services/branch/replace.py`
- Modify: `app/services/read_models/derived/replace_preview.py`
- Modify: `app/services/workflows/application.py`
- Modify: `app/routers/workflows.py`
- Test: `tests/test_branch_service.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Write the failing replace-semantic tests**

```python
def test_branch_replace_only_rewrites_target_bindings() -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])
    mutation = BranchMutationService()
    replace = BranchReplaceService()
    read_service = branch_services()

    mutation.apply(
        BranchRef.dev(sample["dev_version"]),
        {"kind": "import_batch", "import_batch_id": batch["import_batch_id"]},
    )
    BranchRegistryService().ensure_dev_branch("2.4.1", project_id=1)

    other_before = read_service.list_branch_entries(BranchRef.dev("2.4.1"))
    source_before = read_service.list_branch_entries(BranchRef.dev(sample["dev_version"]))

    result = replace.execute(BranchRef.dev(sample["dev_version"]), BranchRef.rel_current())

    rel_after = read_service.list_branch_entries(BranchRef.rel_current())
    source_after = read_service.list_branch_entries(BranchRef.dev(sample["dev_version"]))
    other_after = read_service.list_branch_entries(BranchRef.dev("2.4.1"))

    assert {row["business_key"] for row in rel_after} == {row["business_key"] for row in source_before}
    assert source_after == source_before
    assert other_after == other_before
    assert result["summary"]["final_target_entry_count"] == len(source_before)
    assert "cleanup_binding_count" not in result["summary"]
```

```python
def test_branch_replace_preview_uses_phase_6_summary_fields() -> None:
    reset_demo()
    payload = BranchReplaceService().preview(BranchRef.dev("2.4.3"), BranchRef.rel_current())
    assert "final_target_entry_count" in payload["summary"]
    assert "cleanup_binding_count" not in payload["summary"]
```

- [ ] **Step 2: Run the focused replace tests and verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py::test_branch_replace_only_rewrites_target_bindings tests/test_variant_api.py::test_branch_replace_preview_and_execute_report_rebind_target_when_variant_ids_differ`

Expected: FAIL because replace still performs same-series cleanup, still writes publish-state metadata, and still reports `target_entry_count` plus `cleanup_binding_count`.

- [ ] **Step 3: Delete cleanup behavior and rename the summary contract**

```python
# app/services/branch/policy.py
@dataclass(frozen=True)
class BranchReplacePolicy:
    source_branch_ref: BranchRef
    target_branch_ref: BranchRef

    @classmethod
    def for_branches(cls, source_branch_ref: BranchRef, target_branch_ref: BranchRef) -> BranchReplacePolicy:
        if source_branch_ref.is_dev and target_branch_ref.is_rel:
            return cls(source_branch_ref, target_branch_ref)
        raise ValueError(f"unsupported branch replace pair: {source_branch_ref} -> {target_branch_ref}")
```

```python
# app/services/branch/replace.py
def execute(
    self,
    source_branch_ref: BranchRef,
    target_branch_ref: BranchRef,
    project_id: int = DEFAULT_PROJECT_ID,
) -> dict[str, Any]:
    preview = self.preview(source_branch_ref, target_branch_ref, project_id)
    target_scope_type, target_scope_value = target_branch_ref.as_tuple()
    timestamp = now_iso()
    with get_conn() as conn:
        source_members = self.read_models.select_scope_member_rows(
            project_id,
            ScopeSelector.from_branch(source_branch_ref),
            page=1,
            page_size=None,
            conn=conn,
        )
        removed_target_bindings = self.binding_commands.clear_bindings(
            project_id,
            target_scope_type,
            target_scope_value,
            conn=conn,
        )
        affected_entry_ids = {int(row["entry_id"]) for row in removed_target_bindings}
        for item in source_members:
            entry_id = int(item["entry_id"])
            affected_entry_ids.add(entry_id)
            self.binding_commands.upsert_binding(
                entry_id,
                target_scope_type,
                target_scope_value,
                int(item["variant_id"]),
                timestamp,
                conn=conn,
            )
        for entry_id in sorted(affected_entry_ids):
            self.lifecycle.refresh_orphan_states(entry_id, conn=conn, timestamp=timestamp)
    summary = {
        "source_branch_ref": str(source_branch_ref),
        "target_branch_ref": str(target_branch_ref),
        "final_target_entry_count": preview["summary"]["final_target_entry_count"],
        "added_to_target_count": preview["summary"]["added_to_target_count"],
        "kept_in_target_count": preview["summary"]["kept_in_target_count"],
        "rebind_target_count": preview["summary"]["rebind_target_count"],
        "removed_from_target_count": preview["summary"]["removed_from_target_count"],
    }
    return {"summary": summary, "report_rows": preview["rows"]}
```

```python
# app/services/read_models/derived/replace_preview.py
summary = {
    "final_target_entry_count": len(source_keys),
    "added_to_target_count": len(added),
    "kept_in_target_count": len(kept),
    "rebind_target_count": len(rebind),
    "removed_from_target_count": len(removed),
}
```

- [ ] **Step 4: Re-run the focused replace tests**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py::test_branch_replace_only_rewrites_target_bindings tests/test_variant_api.py::test_branch_replace_preview_and_execute_report_rebind_target_when_variant_ids_differ`

Expected: PASS with source and unrelated branches unchanged, target bindings rewritten in one transaction, and the summary renamed to `final_target_entry_count`.

### Task 4: Remove Candidate Semantics From Frontend Types And Default Branch Selection

**Files:**
- Modify: `frontend/src/domains/branches/types.ts`
- Modify: `frontend/src/domains/branches/api.ts`
- Modify: `frontend/src/domains/projects/types.ts`
- Modify: `frontend/src/app/shell/AppShell.tsx`
- Modify: `frontend/src/pages/branches/BranchOpsPage.tsx`
- Modify: `frontend/src/pages/overview/OverviewPage.tsx`
- Modify: `frontend/src/pages/project/ProjectPage.tsx`
- Test: `tests/e2e/product-app.spec.js`

- [ ] **Step 1: Write the failing UI regression**

```javascript
test("replace flow no longer depends on candidate release metadata", async ({ page }) => {
  await page.goto("/app/project?project=1&lang=fr");
  await expect(page.getByText("candidate")).toHaveCount(0);

  await page.goto("/app/branches?project=1&lang=fr&branch=dev%2F2.4.3&tab=replace");
  await page.getByRole("button", { name: "Preview replace" }).click();
  await expect(page.getByText("final_target_entry_count")).toBeVisible();
  await page.getByRole("button", { name: "Execute replace" }).click();
  await expect(page.getByTestId("runs-page")).toContainText("Branch Replace Execute");
});
```

- [ ] **Step 2: Run the frontend verification and confirm it fails**

Run: `npm run test:e2e`

Expected: FAIL because the shell and branch pages still read `candidate_dev_branch`, still send `mark_as_candidate_release`, and still render candidate badges.

- [ ] **Step 3: Simplify the frontend branch model and default branch logic**

```ts
// frontend/src/domains/branches/types.ts
export type DevBranchSummary = {
  project_id: number;
  version: string;
  version_series: string;
  branch_ref: string;
  entry_count: number;
  bootstrap_state: "not_bootstrapped" | "bootstrapped";
  bootstrapped_at: string | null;
  bootstrap_job_id: number | null;
  bootstrap_import_batch_id: number | null;
  created_at: string;
};

export type BranchMutationInput =
  | {
      kind: "direct";
      changes: BranchMutationChange[];
    }
  | {
      kind: "import_batch";
      import_batch_id: number;
    };
```

```ts
// frontend/src/domains/projects/types.ts
export type ProductStateResponse = {
  project: ProjectSummary;
  schema: ProjectSchema;
  release_summary: Record<string, unknown>;
  dev_branches: DevBranchSummary[];
  imports: ImportBatchSummary[];
  jobs: JobSummary[];
};
```

```ts
// frontend/src/app/shell/AppShell.tsx
const branchRefs = new Set<string>(["rel/current"]);
bootstrap?.dev_branches.forEach((branch) => branchRefs.add(branch.branch_ref));
branchSummary?.branches.forEach((branch) => branchRefs.add(branch.branch_ref));

return bootstrap?.dev_branches[0]?.branch_ref || "rel/current";
```

```tsx
// frontend/src/pages/branches/BranchOpsPage.tsx
const preferredDevBranch = bootstrap?.dev_branches[0]?.branch_ref || null;

runBranchMutation(projectId, normalizedApplyBranchRef, {
  kind: "import_batch",
  import_batch_id: selectedImportBatchId,
});
```

- [ ] **Step 4: Re-run the frontend build and e2e flow**

Run: `npm run build:app`

Expected: PASS with no TypeScript errors and no frontend references to removed candidate or promote fields.

Run: `npm run test:e2e`

Expected: PASS with the replace flow still working and no `candidate` badges or hints remaining in `/app`.

### Task 5: Update Active Docs And Regression Suites To Match Phase 6

**Files:**
- Modify: `docs/system.md`
- Modify: `docs/contracts.md`
- Modify: `docs/workflows.md`
- Modify: `docs/testing.md`
- Modify: `design/branch-infra-phase-map.md`
- Modify: `tests/test_services_architecture.py`
- Modify: `tests/test_branch_service.py`
- Modify: `tests/test_variant_api.py`
- Modify: `tests/e2e/product-app.spec.js`

- [ ] **Step 1: Write the failing docs-architecture assertions**

```python
def test_active_docs_cover_phase_6_replace_cleanup() -> None:
    contracts_doc = _read_doc("docs/contracts.md")
    workflows_doc = _read_doc("docs/workflows.md")
    system_doc = _read_doc("docs/system.md")

    assert "final_target_entry_count" in contracts_doc
    assert "cleanup_binding_count" not in contracts_doc
    assert "candidate_dev_branch" not in contracts_doc
    assert "mark_as_candidate_release" not in contracts_doc
    assert "is_candidate_release" not in system_doc
    assert "promoted_at" not in system_doc
    assert "replace only changes target-branch bindings" in workflows_doc
```

- [ ] **Step 2: Run the doc-oriented regression and verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_services_architecture.py::test_active_docs_cover_phase_6_replace_cleanup`

Expected: FAIL because the active docs still describe candidate metadata, old replace cleanup behavior, and the old replace summary field names.

- [ ] **Step 3: Update the owner docs and the phase map**

```md
<!-- docs/workflows.md -->
- replace is a pure target-binding rewrite
- the live policy only supports `dev/<version> -> rel/current`
- replace preview and execute only change target-branch bindings
- replace summary fields are `final_target_entry_count`, `added_to_target_count`, `kept_in_target_count`, `rebind_target_count`, and `removed_from_target_count`
- replace does not write candidate or promote metadata
```

```md
<!-- docs/contracts.md -->
- `GET /api/projects/{project_id}/state` returns `project`, `schema`, `release_summary`, `dev_branches`, `imports`, and `jobs`
- `POST /api/projects/{project_id}/branches/replace/preview` returns `final_target_entry_count` plus the four replace counters
- mutation input `import_batch` accepts only `import_batch_id`
```

```md
<!-- docs/system.md -->
- `dev_versions` stores branch identity plus bootstrap metadata only
- branch runtime state no longer includes candidate or promote fields
```

- [ ] **Step 4: Run the full targeted regression and docs validation**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py tests/test_variant_api.py tests/test_services_architecture.py`

Expected: PASS for service, API, and doc assertions that cover the Phase 6 cleanup.

Run: `.\.venv\Scripts\python.exe scripts\validate_docs.py`

Expected: PASS with no broken links or stale command references in the active docs.

## Self-Review Checklist

- Spec coverage:
  - pure target-binding rewrite is covered by Task 3
  - candidate or promote metadata removal is covered by Tasks 1, 2, and 4
  - preview and execute contract cleanup is covered by Task 3
  - frontend default-branch derivation cleanup is covered by Task 4
  - active doc alignment is covered by Task 5
- Placeholder scan:
  - no `TODO`, `TBD`, or "implement later" placeholders remain
  - every task includes concrete files, code, and commands
- Type consistency:
  - backend `DevBranchSummary` and frontend `DevBranchSummary` both remove candidate or promote fields
  - backend import-batch mutation input and frontend import-batch mutation input both keep only `import_batch_id`
  - replace summary uses `final_target_entry_count` consistently in preview, execute, tests, and docs

## Execution Handoff

Plan complete and saved to `design/archive/phase-6-branch-to-branch-operations-implementation-plan.md`.

Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
