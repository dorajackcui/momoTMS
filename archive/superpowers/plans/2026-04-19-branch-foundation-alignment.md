# Branch Foundation Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the current branch, variant, and pivot implementation with the approved foundation spec by moving operator-facing branch reads into `read_models`, adding branch-first read contracts, making authority failures explicit, and fixing replace preview semantics.

**Architecture:** The current runtime already contains the core `entry`, `variant`, lifecycle, and pivot primitives. This plan does not rebuild those basics. Instead, it closes the gaps identified in the design spec: branch read ownership still leaks through `app/services/branch`, public read contracts still use `scope` terminology, mutation hides authority failures behind `NOOP` or silent rebind behavior, and replace preview reports key overlap instead of real binding changes.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, pytest, Markdown docs

---

## File Map

### Create

- `app/services/read_models/derived/branch_catalog.py`
  Purpose: own operator-facing branch metadata reads such as release summary, active dev branches, dev branch detail, and candidate branch detail.
- `archive/superpowers/plans/2026-04-19-branch-foundation-alignment.md`
  Purpose: this implementation plan.

### Modify

- `app/services/project/bootstrap.py`
  Purpose: switch bootstrap assembly to the read-model-owned branch catalog view.
- `app/routers/workflows.py`
  Purpose: switch `/branches/dev` routes to the read-model-owned branch catalog view.
- `app/schemas.py`
  Purpose: add branch-first response models for rows, lookup, and replace preview counts.
- `app/routers/scopes_read_models.py`
  Purpose: add canonical branch-first rows and lookup routes, keep scope routes as thin aliases during the transition, and return branch-first payload keys on the new routes.
- `app/services/branch/registry.py`
  Purpose: keep write-facing branch metadata helpers such as `ensure_dev_branch()` and cleanup helpers, while letting operator-facing reads move to `read_models`.
- `app/services/branch/policy.py`
  Purpose: separate content-mutation authority from allowed rebind behavior.
- `app/services/branch/direct_mutation.py`
  Purpose: report explicit authority failures instead of silently returning `NOOP` or rebind results when payloads request forbidden content changes.
- `app/services/branch/import_batch_mutation.py`
  Purpose: mirror the direct-mutation authority behavior for import-batch writes.
- `app/services/read_models/derived/replace_preview.py`
  Purpose: compare source and target bindings by `variant_id`, not only by `business_key`.
- `app/services/branch/replace.py`
  Purpose: expose preview-aligned replace summary fields.
- `app/services/read_models/__init__.py`
  Purpose: export the new branch catalog view.
- `app/services/read_models/derived/__init__.py`
  Purpose: export the new branch catalog view.
- `tests/service_helpers.py`
  Purpose: point service helpers at the new branch catalog view where the tests need operator-facing branch reads.
- `tests/test_services_architecture.py`
  Purpose: lock in the architecture boundaries and doc expectations from the spec.
- `tests/test_variant_refactor_services.py`
  Purpose: keep bootstrap and branch summary query-budget regressions green after the read-model extraction.
- `tests/test_variant_api.py`
  Purpose: add API regression coverage for branch-first rows and lookup routes.
- `tests/test_branch_service.py`
  Purpose: add service regression coverage for authority failures and replace preview semantics.
- `docs/system.md`
  Purpose: describe `branch` as the primary selection-layer term.
- `docs/contracts.md`
  Purpose: describe the canonical branch-first read contracts and updated replace preview payload.
- `docs/workflows.md`
  Purpose: document explicit authority failure reporting and replace preview semantics.

### Existing Baseline To Preserve

- `app/services/variant/entries.py`
  Purpose: stable `entry` identity and lookup.
- `app/services/variant/catalog.py`
  Purpose: live `variant` creation, update, and same-source lookup.
- `app/services/workflows/trash_restore.py`
  Purpose: variant lifecycle operations remain variant-local.
- `app/services/workflows/pivot_review.py`
  Purpose: pivot review remains a constrained variant-state transition.

## Task 1: Move Operator-Facing Branch Reads Into Read Models

**Files:**
- Create: `app/services/read_models/derived/branch_catalog.py`
- Modify: `app/services/read_models/derived/__init__.py`
- Modify: `app/services/read_models/__init__.py`
- Modify: `app/services/project/bootstrap.py`
- Modify: `app/routers/workflows.py`
- Modify: `tests/service_helpers.py`
- Test: `tests/test_services_architecture.py`
- Test: `tests/test_variant_refactor_services.py`

- [ ] **Step 1: Write the failing architecture test**

```python
def test_branch_catalog_view_owns_operator_facing_branch_reads() -> None:
    branch_catalog_path = ROOT / "app/services/read_models/derived/branch_catalog.py"
    assert branch_catalog_path.exists()

    branch_catalog_source = branch_catalog_path.read_text(encoding="utf-8")
    assert "class BranchCatalogView" in branch_catalog_source

    bootstrap_source = (ROOT / "app/services/project/bootstrap.py").read_text(encoding="utf-8")
    assert "BranchCatalogView" in bootstrap_source
    assert "BranchDetailService" not in bootstrap_source
    assert "BranchRegistryService" not in bootstrap_source

    workflows_source = (ROOT / "app/routers/workflows.py").read_text(encoding="utf-8")
    assert "BranchCatalogView" in workflows_source
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_services_architecture.py::test_branch_catalog_view_owns_operator_facing_branch_reads
```

Expected:

```text
FAIL tests/test_services_architecture.py::test_branch_catalog_view_owns_operator_facing_branch_reads
E   AssertionError: assert False
```

- [ ] **Step 3: Add `BranchCatalogView` and switch bootstrap and route consumers**

```python
# app/services/read_models/derived/branch_catalog.py
from __future__ import annotations

from typing import Any

from app.services.branch.models import BranchRef
from app.services.branch.registry import BranchRegistryService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.read_models.datasets.scope_members import ScopeMembershipDataset
from app.services.read_models.selectors import ScopeSelector


class BranchCatalogView:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.registry = BranchRegistryService()
        self.scope_members = ScopeMembershipDataset()

    def release_summary(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        self.projects.require_project(project_id)
        return self.registry.release_summary(project_id, skip_project_check=True)

    def list_dev_branches(self, project_id: int = DEFAULT_PROJECT_ID, *, active_only: bool = True) -> list[dict[str, Any]]:
        self.projects.require_project(project_id)
        return self.registry.list_dev_branches(
            project_id=project_id,
            active_only=active_only,
            skip_project_check=True,
        )

    def get_dev_branch(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        self.projects.require_project(project_id)
        for branch in self.list_dev_branches(project_id=project_id, active_only=False):
            if branch["version"] == version:
                branch_detail = dict(branch)
                branch_detail["entries"] = self.scope_members.list_entry_views(
                    ScopeSelector.from_branch(BranchRef.dev(version)),
                    project_id=project_id,
                )
                return branch_detail
        raise KeyError(f"dev branch not found: {version}")

    def get_candidate_dev_branch(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any] | None:
        self.projects.require_project(project_id)
        for branch in self.list_dev_branches(project_id=project_id, active_only=True):
            if branch["is_candidate_release"]:
                return self.get_dev_branch(branch["version"], project_id=project_id)
        return None
```

```python
# app/services/project/bootstrap.py
from app.services.read_models.derived.branch_catalog import BranchCatalogView


class ProjectBootstrapService:
    def __init__(self) -> None:
        self.branch_catalog = BranchCatalogView()
        self.project_service = ProjectService()
        self.import_service = ImportService()
        self.job_service = JobService()

    def get_state(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        project = self.project_service.require_project(project_id)
        dev_branches = self.branch_catalog.list_dev_branches(project_id=project_id, active_only=True)
        return {
            "project": project,
            "schema": self.project_service.get_schema(project_id),
            "release_summary": self.branch_catalog.release_summary(project_id),
            "candidate_dev_branch": self.branch_catalog.get_candidate_dev_branch(project_id),
            "dev_branches": dev_branches,
            "imports": self.import_service.list_batches(project_id=project_id),
            "jobs": self.job_service.list_jobs(project_id=project_id),
        }
```

```python
# app/routers/workflows.py
from app.services.read_models.derived.branch_catalog import BranchCatalogView


@router.get("/api/projects/{project_id}/branches/dev", response_model=list[DevBranchSummary])
def project_list_dev_branches(project_id: int) -> list[DevBranchSummary]:
    return handle_errors(
        lambda: [DevBranchSummary(**item) for item in BranchCatalogView().list_dev_branches(project_id=project_id)]
    )


@router.get("/api/projects/{project_id}/branches/dev/{version}", response_model=DevBranchDetail)
def project_get_dev_branch(project_id: int, version: str) -> DevBranchDetail:
    return handle_errors(lambda: DevBranchDetail(**BranchCatalogView().get_dev_branch(version, project_id)))
```

- [ ] **Step 4: Run the focused regression set**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_services_architecture.py tests/test_variant_refactor_services.py
```

Expected:

```text
PASS tests/test_services_architecture.py
PASS tests/test_variant_refactor_services.py
```

- [ ] **Step 5: Commit**

```bash
git add app/services/read_models/derived/branch_catalog.py app/services/read_models/derived/__init__.py app/services/read_models/__init__.py app/services/project/bootstrap.py app/routers/workflows.py tests/service_helpers.py tests/test_services_architecture.py tests/test_variant_refactor_services.py
git commit -m "refactor: move branch metadata reads into read models"
```

## Task 2: Add Canonical Branch-First Rows And Lookup Routes

**Files:**
- Modify: `app/schemas.py`
- Modify: `app/routers/scopes_read_models.py`
- Test: `tests/test_variant_api.py`
- Test: `tests/test_services_architecture.py`

- [ ] **Step 1: Write the failing API regression**

```python
def test_branch_rows_and_lookup_routes_match_existing_scope_routes() -> None:
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
                    "mark_as_candidate_release": True,
                },
            },
        )
        assert wait_for_job(client, mutation.json())["job"]["status"] == "success"

        branch_rows = client.get(f"/api/projects/1/branches/dev/{sample['dev_version']}/rows")
        assert branch_rows.status_code == 200
        assert branch_rows.json()["branch_ref"] == f"dev/{sample['dev_version']}"

        scope_rows = client.get(f"/api/projects/1/scopes/dev/{sample['dev_version']}/rows")
        assert branch_rows.json()["rows"] == scope_rows.json()["rows"]

        branch_lookup = client.get(
            f"/api/projects/1/branches/dev/{sample['dev_version']}/lookup",
            params={"business_key": "dev.mutable"},
        )
        assert branch_lookup.status_code == 200
        assert branch_lookup.json()["branch_ref"] == f"dev/{sample['dev_version']}"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py::test_branch_rows_and_lookup_routes_match_existing_scope_routes
```

Expected:

```text
FAIL tests/test_variant_api.py::test_branch_rows_and_lookup_routes_match_existing_scope_routes
E   assert 404 == 200
```

- [ ] **Step 3: Add branch-first response models and routes**

```python
# app/schemas.py
class BranchRowsResponse(BaseModel):
    branch_ref: str
    rows: list["ProjectVariantRow"] = Field(default_factory=list)
    total_rows: int = 0
    page: int = 1
    page_size: int = 0


class BranchLookupResponse(BaseModel):
    branch_ref: str
    mode: Literal["business_key", "source"]
    value: str
    rows: list["ProjectVariantRow"] = Field(default_factory=list)
```

```python
# app/routers/scopes_read_models.py
def _branch_rows_payload(
    project_id: int,
    branch_ref: str,
    *,
    search_business_key: str | None,
    search_source: str | None,
    page: int,
    page_size: int | None,
) -> dict[str, Any]:
    selector = ScopeSelector.parse(branch_ref)
    payload = ScopeMembershipDataset().list(
        selector,
        filters=VariantFilter(
            search_business_key=search_business_key,
            search_source=search_source,
        ),
        project_id=project_id,
        page=page,
        page_size=page_size,
    )
    payload["branch_ref"] = str(selector)
    payload.pop("scope_ref", None)
    return payload


@router.get("/api/projects/{project_id}/branches/{branch_ref:path}/rows", response_model=BranchRowsResponse)
def project_branch_rows(
    project_id: int,
    branch_ref: str,
    search_business_key: str | None = Query(default=None),
    search_source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> BranchRowsResponse:
    return handle_errors(
        lambda: BranchRowsResponse(
            **_branch_rows_payload(
                project_id,
                branch_ref,
                search_business_key=search_business_key,
                search_source=search_source,
                page=page,
                page_size=page_size,
            )
        )
    )
```

```python
# app/routers/scopes_read_models.py
def _branch_lookup_payload(
    project_id: int,
    branch_ref: str,
    *,
    business_key: str | None,
    source: str | None,
) -> dict[str, Any]:
    selector = ScopeSelector.parse(branch_ref)
    payload = ScopeMembershipDataset().lookup(
        selector,
        project_id=project_id,
        business_key=business_key,
        source=source,
    )
    payload["branch_ref"] = str(selector)
    payload.pop("scope_ref", None)
    return payload


@router.get("/api/projects/{project_id}/branches/{branch_ref:path}/lookup", response_model=BranchLookupResponse)
def project_branch_lookup(
    project_id: int,
    branch_ref: str,
    business_key: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> BranchLookupResponse:
    return handle_errors(
        lambda: BranchLookupResponse(
            **_branch_lookup_payload(
                project_id,
                branch_ref,
                business_key=business_key,
                source=source,
            )
        )
    )
```

- [ ] **Step 4: Run the route regression set**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py::test_branch_rows_and_lookup_routes_match_existing_scope_routes tests/test_variant_api.py::test_scope_routes_and_removed_compatibility_surface
```

Expected:

```text
PASS tests/test_variant_api.py::test_branch_rows_and_lookup_routes_match_existing_scope_routes
PASS tests/test_variant_api.py::test_scope_routes_and_removed_compatibility_surface
```

- [ ] **Step 5: Commit**

```bash
git add app/schemas.py app/routers/scopes_read_models.py tests/test_variant_api.py tests/test_services_architecture.py
git commit -m "feat: add branch-first rows and lookup routes"
```

## Task 3: Make Authority Failures Explicit In Mutation Results

**Files:**
- Modify: `app/services/branch/policy.py`
- Modify: `app/services/branch/direct_mutation.py`
- Modify: `app/services/branch/import_batch_mutation.py`
- Test: `tests/test_branch_service.py`

- [ ] **Step 1: Write the failing service regression**

```python
def test_lower_authority_branch_reports_forbidden_when_payload_requests_content_change() -> None:
    reset_demo()
    services = branch_services()
    entry = services.entries.get_or_create_entry("authority.explicit", project_id=1)
    variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "authority.xlsx",
            "Shared source",
            {"fr": "Higher authority"},
            {"context": "authority"},
        ),
    )
    services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.2"), variant_id)

    result = BranchMutationService().apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "authority.explicit",
                    "source": "Shared source",
                    "translations_by_lang": {"fr": "Attempted overwrite"},
                }
            ],
        },
    )

    assert result["report_rows"][0]["status"] == "FORBIDDEN_BY_AUTHORITY"
    assert result["summary"]["forbidden_by_authority_count"] == 1
    assert services.catalog.get_variant(variant_id)["translations"]["fr"] == "Higher authority"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py::test_lower_authority_branch_reports_forbidden_when_payload_requests_content_change
```

Expected:

```text
FAIL tests/test_branch_service.py::test_lower_authority_branch_reports_forbidden_when_payload_requests_content_change
E   AssertionError: assert 'BOUND_EXISTING_VARIANT' == 'FORBIDDEN_BY_AUTHORITY'
```

- [ ] **Step 3: Split authority decisions into content mutation vs rebind**

```python
# app/services/branch/policy.py
class AuthorityPolicy:
    @classmethod
    def can_mutate_variant_content(cls, actor_branch_ref: BranchRef, bound_branch_refs: list[BranchRef]) -> bool:
        if not bound_branch_refs:
            return True
        actor_key = cls.key_for_branch(actor_branch_ref)
        highest_bound = max(cls.key_for_branch(branch_ref) for branch_ref in bound_branch_refs)
        return actor_key >= highest_bound

    @classmethod
    def content_mutation_status(cls, actor_branch_ref: BranchRef, bound_branch_refs: list[BranchRef]) -> str | None:
        if cls.can_mutate_variant_content(actor_branch_ref, bound_branch_refs):
            return None
        return "FORBIDDEN_BY_AUTHORITY"


@dataclass(frozen=True)
class BranchMutationPolicy:
    branch_ref: BranchRef

    def content_mutation_status(self, actor_branch_ref: BranchRef, bound_branch_refs: list[BranchRef]) -> str | None:
        return AuthorityPolicy.content_mutation_status(actor_branch_ref, bound_branch_refs)
```

```python
# app/services/branch/direct_mutation.py
if requested_source == current_variant["source"]:
    merged = self.resolution.merged_variant_payload(current_variant, change, requested_source)
    if self.resolution.variant_matches(current_variant, merged):
        return {
            "business_key": business_key,
            "branch_ref": str(branch_ref),
            "variant_id": int(current_variant["variant_id"]),
            "status": "NOOP",
            "created_entry": created_entry,
        }

    bound_branch_refs = self.resolution.bound_branch_refs_for_variant(
        self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
        int(current_variant["variant_id"]),
    )
    forbidden_status = policy.content_mutation_status(branch_ref, bound_branch_refs)
    if forbidden_status is not None:
        return {
            "business_key": business_key,
            "branch_ref": str(branch_ref),
            "variant_id": int(current_variant["variant_id"]),
            "status": forbidden_status,
            "created_entry": created_entry,
        }
```

```python
# app/services/branch/import_batch_mutation.py
if source_variant is not None and not self.resolution.variant_matches(source_variant, merged):
    target_variant_id = int(source_variant["variant_id"])
    bound_branch_refs = self.resolution.bound_branch_refs_for_variant(bindings, target_variant_id)
    forbidden_status = BranchMutationPolicy.for_branch(target_branch).content_mutation_status(
        target_branch,
        bound_branch_refs,
    )
    if forbidden_status is not None:
        return forbidden_status
```

- [ ] **Step 4: Run the mutation regression set**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py tests/test_io_flows.py
```

Expected:

```text
PASS tests/test_branch_service.py
PASS tests/test_io_flows.py
```

- [ ] **Step 5: Commit**

```bash
git add app/services/branch/policy.py app/services/branch/direct_mutation.py app/services/branch/import_batch_mutation.py tests/test_branch_service.py
git commit -m "feat: report explicit authority failures for branch mutation"
```

## Task 4: Make Replace Preview Describe Real Binding Changes

**Files:**
- Modify: `app/schemas.py`
- Modify: `app/services/read_models/derived/replace_preview.py`
- Modify: `app/services/branch/replace.py`
- Test: `tests/test_branch_service.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Write the failing replace-preview regression**

```python
def test_branch_replace_preview_reports_rebind_target_when_variant_ids_differ() -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    BranchMutationService().apply(
        BranchRef.dev(sample["dev_version"]),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
            "mark_as_candidate_release": True,
        },
    )

    preview = BranchReplaceService().preview(BranchRef.dev(sample["dev_version"]), BranchRef.rel_current())
    statuses = {row["business_key"]: row["status"] for row in preview["report_rows"]}

    assert statuses["rel.locked.changed"] == "REBIND_TARGET"
    assert preview["rebind_target_count"] >= 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py::test_branch_replace_preview_reports_rebind_target_when_variant_ids_differ
```

Expected:

```text
FAIL tests/test_branch_service.py::test_branch_replace_preview_reports_rebind_target_when_variant_ids_differ
E   AssertionError: assert 'KEEP_IN_TARGET' == 'REBIND_TARGET'
```

- [ ] **Step 3: Compare source and target rows by binding identity**

```python
# app/schemas.py
class BranchReplacePreview(BaseModel):
    source_branch_ref: str
    target_branch_ref: str
    target_entry_count: int
    added_to_target_count: int
    kept_in_target_count: int
    rebind_target_count: int
    removed_from_target_count: int
    cleanup_binding_count: int
    report_rows: list[dict[str, Any]] = Field(default_factory=list)
```

```python
# app/services/read_models/derived/replace_preview.py
source_rows = {item["business_key"]: item for item in source_payload["rows"]}
target_rows = {item["business_key"]: item for item in target_payload["rows"]}

report_rows: list[dict[str, Any]] = []
added = kept = rebind = removed = 0

for business_key in sorted(set(source_rows) | set(target_rows)):
    source_row = source_rows.get(business_key)
    target_row = target_rows.get(business_key)
    if source_row is not None and target_row is None:
        added += 1
        report_rows.append({"business_key": business_key, "status": "ADD_TO_TARGET"})
    elif source_row is not None and target_row is not None and int(source_row["variant_id"]) != int(target_row["variant_id"]):
        rebind += 1
        report_rows.append(
            {
                "business_key": business_key,
                "status": "REBIND_TARGET",
                "source_variant_id": int(source_row["variant_id"]),
                "target_variant_id": int(target_row["variant_id"]),
            }
        )
    elif source_row is not None and target_row is not None:
        kept += 1
        report_rows.append({"business_key": business_key, "status": "KEEP_IN_TARGET"})
    else:
        removed += 1
        report_rows.append({"business_key": business_key, "status": "REMOVE_FROM_TARGET"})
```

```python
# app/services/branch/replace.py
summary = {
    "source_branch_ref": str(source_branch_ref),
    "target_branch_ref": str(target_branch_ref),
    "target_entry_count": preview["target_entry_count"],
    "added_to_target_count": preview["added_to_target_count"],
    "kept_in_target_count": preview["kept_in_target_count"],
    "rebind_target_count": preview["rebind_target_count"],
    "removed_from_target_count": preview["removed_from_target_count"],
    "cleanup_binding_count": removed_binding_count,
    "stages": [
        {
            "stage": "execute_branch_replace",
            "elapsed_ms": int((perf_counter() - started) * 1000),
            "meta": {
                "source_branch_ref": str(source_branch_ref),
                "target_branch_ref": str(target_branch_ref),
                "target_entry_count": preview["target_entry_count"],
            },
        }
    ],
}
```

- [ ] **Step 4: Run the replace regression set**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py::test_branch_replace_preview_reports_rebind_target_when_variant_ids_differ tests/test_variant_api.py::test_scope_routes_and_removed_compatibility_surface
```

Expected:

```text
PASS tests/test_branch_service.py::test_branch_replace_preview_reports_rebind_target_when_variant_ids_differ
PASS tests/test_variant_api.py::test_scope_routes_and_removed_compatibility_surface
```

- [ ] **Step 5: Commit**

```bash
git add app/schemas.py app/services/read_models/derived/replace_preview.py app/services/branch/replace.py tests/test_branch_service.py tests/test_variant_api.py
git commit -m "fix: align branch replace preview with execute semantics"
```

## Task 5: Update Active Docs And Lock The New Contract In Tests

**Files:**
- Modify: `docs/system.md`
- Modify: `docs/contracts.md`
- Modify: `docs/workflows.md`
- Modify: `tests/test_services_architecture.py`
- Test: `scripts/validate_docs.py`

- [ ] **Step 1: Write the failing doc regression**

```python
def test_active_docs_describe_branch_first_routes_and_authority_rules() -> None:
    system_doc = (ROOT / "docs/system.md").read_text(encoding="utf-8")
    contracts_doc = (ROOT / "docs/contracts.md").read_text(encoding="utf-8")
    workflows_doc = (ROOT / "docs/workflows.md").read_text(encoding="utf-8")

    assert "`branch` is the selection layer" in system_doc
    assert "/api/projects/{project_id}/branches/{branch_ref:path}/rows" in contracts_doc
    assert "/api/projects/{project_id}/branches/{branch_ref:path}/lookup" in contracts_doc
    assert "FORBIDDEN_BY_AUTHORITY" in workflows_doc
    assert "REBIND_TARGET" in workflows_doc
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_services_architecture.py::test_active_docs_describe_branch_first_routes_and_authority_rules
```

Expected:

```text
FAIL tests/test_services_architecture.py::test_active_docs_describe_branch_first_routes_and_authority_rules
E   AssertionError
```

- [ ] **Step 3: Update the active docs to match the aligned model**

```markdown
<!-- docs/system.md -->
- `branch` is the primary operator-facing selection-layer term
- `scope` remains an internal selector term only where legacy implementation still requires it
- `variant` remains the live content entity under one `entry`
- `pivot` remains variant-local workflow state
```

```markdown
<!-- docs/contracts.md -->
- `GET /api/projects/{project_id}/branches/{branch_ref:path}/rows`: canonical branch catalog read
- `GET /api/projects/{project_id}/branches/{branch_ref:path}/lookup`: canonical branch lookup read
- `GET /api/projects/{project_id}/scopes/{scope_ref:path}/rows`: compatibility alias during transition
- `GET /api/projects/{project_id}/scopes/{scope_ref:path}/lookup`: compatibility alias during transition
- `POST /api/projects/{project_id}/branches/replace/preview`: returns `ADD_TO_TARGET`, `KEEP_IN_TARGET`, `REBIND_TARGET`, and `REMOVE_FROM_TARGET`
```

```markdown
<!-- docs/workflows.md -->
- when a branch payload requests a content change on a variant protected by higher branch authority, mutation reports `FORBIDDEN_BY_AUTHORITY`
- authority-blocked writes are not folded into `NOOP`
- replace preview reports binding change semantics, not only business-key overlap
- `REBIND_TARGET` means the same `business_key` exists on both sides but the target binding will switch to a different `variant_id`
```

- [ ] **Step 4: Run docs and architecture verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_services_architecture.py
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected:

```text
PASS tests/test_services_architecture.py
PASS docs validation with no broken routes, links, or file references
```

- [ ] **Step 5: Commit**

```bash
git add docs/system.md docs/contracts.md docs/workflows.md tests/test_services_architecture.py
git commit -m "docs: align branch foundation contracts and workflow rules"
```

## Final Verification

After all tasks land, run the branch-focused regression matrix from the repo root.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_service.py tests/test_variant_api.py tests/test_services_architecture.py tests/test_variant_refactor_services.py tests/test_io_flows.py
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected:

```text
PASS branch service, branch API, architecture, refactor, and IO flow regressions
PASS docs validation
```

## Spec Coverage Check

- Read-model ownership gap: covered by Task 1.
- Branch-first read contracts: covered by Task 2.
- Branch authority phase before mutation finalization: covered by Task 3.
- Replace preview vs execute semantic mismatch: covered by Task 4.
- Active docs drift and branch-first terminology: covered by Task 5.
- Existing entry, variant, lifecycle, and pivot primitives are intentionally preserved and tightened through doc and regression updates instead of being rebuilt from scratch in this plan.
