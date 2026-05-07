# Variant Grid Header Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build server-backed WPS/Excel-style header filters for every visible variant grid field, with 50-row pages and 100-value filter option lists for projects with 300k-500k live variants.

**Architecture:** Add rich POST grid query endpoints beside the existing GET rows APIs, keeping the query service in `app/services/read_models/`. The frontend switches browse grids to the POST contract, keeps Workspace filter state in one URL parameter, and renders a header filter popover for each visible filterable column.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, React 19, TypeScript, TanStack Query, React Data Grid, Playwright.

---

## Spec And Repo Context

- Design spec: `design/2026-05-07-variant-grid-filter-design.md`
- Runtime owner docs to update during implementation:
  - `docs/contracts.md` for new routes, request/response payloads, and frontend contract.
  - `docs/system.md` for `SCHEMA_VERSION` and new read/query index facts if `app/db.py` changes.
- Verification guidance: `docs/testing.md`
- Closeout checklist: `code_review.md`

Existing behavior to preserve:

- `/app` remains the only operator-facing product surface.
- `GET /workbench` and `GET /variant-workbench` stay `410 Gone`.
- Existing GET row routes remain compatible:
  - `GET /api/projects/{project_id}/variants`
  - `GET /api/projects/{project_id}/branches/{branch_ref:path}/rows`
  - `GET /api/projects/{project_id}/scopes/{scope_ref:path}/rows`
- Public APIs stay project-scoped under `/api/projects/{project_id}/...`.
- Branch writes remain under existing mutation/replace/trash routes.

## File Map

Backend:

- Modify `app/schemas.py`
  - add request and response models for rich grid row queries and filter options.
- Modify `app/db.py`
  - bump `SCHEMA_VERSION` from `variant-v12` to `variant-v13`;
  - add translation and remark lookup indexes.
- Create `app/services/read_models/grid_filters.py`
  - validate column references against project schema;
  - normalize filter request values;
  - clamp row page size to 50 and option limit to 100;
  - expose typed filter/spec objects consumed by repository queries.
- Modify `app/services/read_models/repository.py`
  - add rich grid row SQL selection and count;
  - add rich grid distinct option SQL selection.
- Modify `app/services/read_models/datasets/live_variants.py`
  - add project-scope rich row and option facades.
- Modify `app/services/read_models/datasets/scope_members.py`
  - add branch-scope rich row and option facades.
- Modify `app/routers/inspection.py`
  - add `POST /api/projects/{project_id}/variants/query`;
  - add `POST /api/projects/{project_id}/variants/filter-options`.
- Modify `tests/test_variant_api.py`
  - add route and behavior coverage.
- Modify `tests/test_bulk_seed.py`
  - add index coverage.

Frontend:

- Modify `frontend/src/domains/variants/types.ts`
  - add rich grid request and response types.
- Modify `frontend/src/domains/variants/api.ts`
  - add POST helpers for row query and option query.
- Create `frontend/src/shared/ui/variantGridFilters.ts`
  - shared column ids, URL serialization, request conversion helpers.
- Modify `frontend/src/shared/ui/VariantGrid.tsx`
  - replace inline header inputs with filter buttons and popovers;
  - load distinct options per column;
  - apply filters only on Apply or Enter.
- Modify `frontend/src/shared/ui/VariantGrid.module.css`
  - styles for header filter button, popover, active state, checklist, and clear-all control.
- Modify `frontend/src/pages/workspace/WorkspacePage.tsx`
  - use rich POST query;
  - keep filter state in the URL;
  - page size 50.
- Modify `frontend/src/pages/release/ReleasePage.tsx`
  - use rich POST query with branch scope;
  - local filter state;
  - page size 50.
- Modify `frontend/src/pages/dev/BranchDetail.tsx`
  - use rich POST query with branch scope;
  - local filter state;
  - page size 50.
- Modify `tests/e2e/product-app.spec.js`
  - update old variants GET route expectations;
  - add header filter interaction coverage.

Docs:

- Modify `docs/contracts.md`
  - document new POST APIs and frontend contract.
- Modify `docs/system.md`
  - update current schema version and index facts if indexes are added.

---

### Task 1: Backend Contracts, Validation Models, And Indexes

**Files:**

- Modify `tests/test_bulk_seed.py`
- Modify `tests/test_variant_api.py`
- Modify `app/db.py`
- Modify `app/schemas.py`
- Create `app/services/read_models/grid_filters.py`

- [ ] **Step 1: Add failing index coverage**

Add this test after `test_scope_bindings_entry_variant_index_exists` in `tests/test_bulk_seed.py`:

```python
def test_variant_grid_filter_indexes_exist() -> None:
    reset_database()
    with get_conn() as conn:
        translation_indexes = {
            row["name"]
            for row in conn.execute("PRAGMA index_list('variant_translations')").fetchall()
        }
        remark_indexes = {
            row["name"]
            for row in conn.execute("PRAGMA index_list('variant_remarks')").fetchall()
        }
    assert "idx_variant_translations_lang_variant" in translation_indexes
    assert "idx_variant_translations_lang_text_variant" in translation_indexes
    assert "idx_variant_remarks_key_variant" in remark_indexes
    assert "idx_variant_remarks_key_value_variant" in remark_indexes
```

- [ ] **Step 2: Run the index test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_bulk_seed.py::test_variant_grid_filter_indexes_exist
```

Expected: FAIL because the four new index names do not exist.

- [ ] **Step 3: Add failing request validation coverage**

Add these imports near the top of `tests/test_variant_api.py`:

```python
from app.schemas import VariantGridColumnRef, VariantGridFilterRequest
from app.services.read_models.grid_filters import build_grid_query
```

Add this test near the project variants route tests:

```python
def test_variant_grid_filter_request_validates_columns_against_schema() -> None:
    reset_demo()
    request = VariantGridFilterRequest(
        scope={"kind": "project"},
        state="all",
        filters=[
            {
                "column": {"kind": "translation", "name": "fr"},
                "text": "Bonjour",
                "values": [],
            }
        ],
        page=1,
        page_size=500,
    )
    spec = build_grid_query(1, request)
    assert spec.page == 1
    assert spec.page_size == 50
    assert spec.scope_selector is None
    assert spec.state == "all"
    assert spec.filters[0].column == VariantGridColumnRef(kind="translation", name="fr")

    bad_request = VariantGridFilterRequest(
        scope={"kind": "project"},
        filters=[
            {
                "column": {"kind": "translation", "name": "missing_lang"},
                "text": "",
                "values": [],
            }
        ],
    )
    try:
        build_grid_query(1, bad_request)
    except ValueError as exc:
        assert "unknown translation column for project: missing_lang" in str(exc)
    else:
        raise AssertionError("expected unknown translation column to fail")
```

- [ ] **Step 4: Run validation test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py::test_variant_grid_filter_request_validates_columns_against_schema
```

Expected: FAIL because `VariantGridColumnRef`, `VariantGridFilterRequest`, and `build_grid_query` do not exist.

- [ ] **Step 5: Add DB indexes**

In `app/db.py`, change:

```python
SCHEMA_VERSION = "variant-v12"
```

to:

```python
SCHEMA_VERSION = "variant-v13"
```

After the `CREATE TABLE variant_translations` statement, add:

```sql
        CREATE INDEX idx_variant_translations_lang_variant
        ON variant_translations(lang, variant_id);
        CREATE INDEX idx_variant_translations_lang_text_variant
        ON variant_translations(lang, target_text, variant_id);
```

After the `CREATE TABLE variant_remarks` statement, add:

```sql
        CREATE INDEX idx_variant_remarks_key_variant
        ON variant_remarks(remark_key, variant_id);
        CREATE INDEX idx_variant_remarks_key_value_variant
        ON variant_remarks(remark_key, remark_value, variant_id);
```

- [ ] **Step 6: Add schema models**

In `app/schemas.py`, add these models after `ProjectVariantsResponse`:

```python
class VariantGridColumnRef(BaseModel):
    kind: Literal["field", "translation", "remark"]
    name: str


class VariantGridScope(BaseModel):
    kind: Literal["project", "branch"]
    branch_ref: str | None = None


class VariantGridColumnFilter(BaseModel):
    column: VariantGridColumnRef
    text: str | None = None
    values: list[str | None] = Field(default_factory=list)


class VariantGridQueryRequest(BaseModel):
    scope: VariantGridScope
    state: Literal["active", "orphan", "all"] = "active"
    filters: list[VariantGridColumnFilter] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1)


class ProjectVariantsQueryResponse(ProjectVariantsResponse):
    has_next_page: bool = False
    total_rows_exact: bool = True


class VariantGridFilterRequest(VariantGridQueryRequest):
    target_column: VariantGridColumnRef | None = None
    option_search: str | None = None
    limit: int = Field(default=100, ge=1)


class VariantFilterOptionValue(BaseModel):
    value: str | None = None
    label: str
    count: int | None = None


class VariantFilterOptionsResponse(BaseModel):
    values: list[VariantFilterOptionValue] = Field(default_factory=list)
    limit: int = 100
    has_more: bool = False
```

- [ ] **Step 7: Add grid filter domain helpers**

Create `app/services/read_models/grid_filters.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.schemas import (
    VariantGridColumnFilter,
    VariantGridColumnRef,
    VariantGridFilterRequest,
    VariantGridQueryRequest,
)
from app.services.branch.models import BranchRef
from app.services.project.service import ProjectService
from app.services.read_models.selectors import ProjectLiveState, ScopeSelector
from app.services.shared.io import normalize_non_content_value


GRID_FIELD_NAMES = frozenset({
    "business_key",
    "file_name",
    "source",
    "branch",
    "state",
    "pivot_status",
})
MAX_GRID_PAGE_SIZE = 50
MAX_FILTER_OPTION_LIMIT = 100


@dataclass(frozen=True)
class GridColumnFilter:
    column: VariantGridColumnRef
    text: str
    values: tuple[str | None, ...]


@dataclass(frozen=True)
class GridQuerySpec:
    project_id: int
    scope_selector: ScopeSelector | None
    state: ProjectLiveState
    filters: tuple[GridColumnFilter, ...]
    page: int
    page_size: int


@dataclass(frozen=True)
class GridOptionsSpec:
    query: GridQuerySpec
    target_column: VariantGridColumnRef
    option_search: str
    limit: int


def build_grid_query(
    project_id: int,
    request: VariantGridQueryRequest,
    *,
    projects: ProjectService | None = None,
) -> GridQuerySpec:
    service = projects or ProjectService()
    schema = service.get_schema(project_id)
    scope_selector = _scope_selector(request)
    return GridQuerySpec(
        project_id=project_id,
        scope_selector=scope_selector,
        state=request.state if scope_selector is None else "active",
        filters=tuple(_validated_filter(item, schema) for item in request.filters),
        page=max(request.page, 1),
        page_size=min(max(request.page_size, 1), MAX_GRID_PAGE_SIZE),
    )


def build_grid_options(
    project_id: int,
    request: VariantGridFilterRequest,
    *,
    projects: ProjectService | None = None,
) -> GridOptionsSpec:
    if request.target_column is None:
        raise ValueError("target_column is required")
    service = projects or ProjectService()
    schema = service.get_schema(project_id)
    query = build_grid_query(project_id, request, projects=service)
    return GridOptionsSpec(
        query=query,
        target_column=_validated_column(request.target_column, schema),
        option_search=normalize_non_content_value(request.option_search).lower(),
        limit=min(max(request.limit, 1), MAX_FILTER_OPTION_LIMIT),
    )


def filters_excluding_target(
    filters: tuple[GridColumnFilter, ...],
    target_column: VariantGridColumnRef,
) -> tuple[GridColumnFilter, ...]:
    return tuple(item for item in filters if item.column != target_column)


def _scope_selector(request: VariantGridQueryRequest) -> ScopeSelector | None:
    if request.scope.kind == "project":
        return None
    branch_ref = normalize_non_content_value(request.scope.branch_ref)
    if not branch_ref:
        raise ValueError("branch_ref is required for branch scope")
    return ScopeSelector.from_branch(BranchRef.parse(branch_ref))


def _validated_filter(
    item: VariantGridColumnFilter,
    schema: dict,
) -> GridColumnFilter:
    return GridColumnFilter(
        column=_validated_column(item.column, schema),
        text=normalize_non_content_value(item.text).lower(),
        values=tuple(_normalized_value(value) for value in item.values),
    )


def _validated_column(column: VariantGridColumnRef, schema: dict) -> VariantGridColumnRef:
    normalized_name = normalize_non_content_value(column.name)
    normalized = VariantGridColumnRef(kind=column.kind, name=normalized_name)
    if normalized.kind == "field":
        if normalized.name not in GRID_FIELD_NAMES:
            raise ValueError(f"unknown grid field for project: {normalized.name}")
        return normalized
    if normalized.kind == "translation":
        if normalized.name not in schema["translation_columns"]:
            raise ValueError(f"unknown translation column for project: {normalized.name}")
        return normalized
    if normalized.kind == "remark":
        if normalized.name not in schema["remark_columns"]:
            raise ValueError(f"unknown remark column for project: {normalized.name}")
        return normalized
    raise ValueError(f"unsupported grid column kind: {normalized.kind}")


def _normalized_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_non_content_value(value)
    return normalized if normalized else None
```

- [ ] **Step 8: Run Task 1 tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_bulk_seed.py::test_variant_grid_filter_indexes_exist tests/test_variant_api.py::test_variant_grid_filter_request_validates_columns_against_schema
```

Expected: both tests PASS.

- [ ] **Step 9: Commit Task 1**

Run:

```powershell
git add app/db.py app/schemas.py app/services/read_models/grid_filters.py tests/test_bulk_seed.py tests/test_variant_api.py
git commit -m "feat: add variant grid filter contracts"
```

---

### Task 2: Backend Rich Row Query Endpoint

**Files:**

- Modify `tests/test_variant_api.py`
- Modify `app/services/read_models/repository.py`
- Modify `app/services/read_models/datasets/live_variants.py`
- Modify `app/services/read_models/datasets/scope_members.py`
- Modify `app/routers/inspection.py`

- [ ] **Step 1: Add failing route coverage for row filters**

Add this helper near `create_bound_variant` in `tests/test_variant_api.py`:

```python
def create_bound_variant_with_remarks(
    *,
    project_id: int,
    business_key: str,
    source: str,
    file_name: str,
    translations: dict[str, str],
    remarks: dict[str, str],
    branch_refs: list[BranchRef],
) -> int:
    entries = EntryService()
    catalog = VariantCatalogService()
    bindings = VariantStateCoordinator()
    entry = entries.get_or_create_entry(business_key, project_id=project_id)
    variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        catalog.build_content(file_name, source, translations, remarks),
    )
    for branch_ref in branch_refs:
        if branch_ref.is_dev:
            BranchRegistryService().ensure_dev_branch(branch_ref.version, project_id=project_id)
        bindings.bind(int(entry["entry_id"]), branch_ref, variant_id)
    return variant_id
```

Add this test near the project variants route tests:

```python
def test_project_variants_query_filters_every_column_family_and_caps_page_size() -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Grid Filter Query Project",
        ["fr", "en"],
        ["context"],
    )
    project_id = int(project["project_id"])
    create_bound_variant_with_remarks(
        project_id=project_id,
        business_key="rose.red",
        source="A red rose blooms",
        file_name="flowers.xlsx",
        translations={"fr": "Rose rouge", "en": "Red rose"},
        remarks={"context": "garden"},
        branch_refs=[BranchRef.rel_current()],
    )
    create_bound_variant_with_remarks(
        project_id=project_id,
        business_key="rose.white",
        source="A white rose fades",
        file_name="flowers.xlsx",
        translations={"fr": "Rose blanche", "en": "White rose"},
        remarks={"context": "vase"},
        branch_refs=[BranchRef.dev("2.5.0")],
    )
    create_bound_variant_with_remarks(
        project_id=project_id,
        business_key="lily.blue",
        source="A blue lily",
        file_name="lilies.xlsx",
        translations={"fr": "Lys bleu", "en": "Blue lily"},
        remarks={"context": "garden"},
        branch_refs=[BranchRef.rel_current()],
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/projects/{project_id}/variants/query",
            json={
                "scope": {"kind": "project"},
                "state": "all",
                "filters": [
                    {"column": {"kind": "field", "name": "source"}, "text": "rose", "values": []},
                    {"column": {"kind": "translation", "name": "fr"}, "text": "rouge", "values": []},
                    {"column": {"kind": "remark", "name": "context"}, "text": "", "values": ["garden"]},
                    {"column": {"kind": "field", "name": "branch"}, "text": "", "values": ["rel/current"]},
                    {"column": {"kind": "field", "name": "state"}, "text": "", "values": ["active"]},
                    {"column": {"kind": "field", "name": "pivot_status"}, "text": "", "values": ["init"]},
                    {"column": {"kind": "field", "name": "file_name"}, "text": "", "values": ["flowers.xlsx"]},
                ],
                "page": 1,
                "page_size": 500,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 50
    assert payload["total_rows_exact"] is True
    assert payload["has_next_page"] is False
    assert [row["business_key"] for row in payload["rows"]] == ["rose.red"]
    assert payload["rows"][0]["translations"]["fr"] == "Rose rouge"
    assert payload["rows"][0]["remarks"]["context"] == "garden"
```

Add branch-scope coverage:

```python
def test_project_variants_query_branch_scope_ignores_project_state_and_supports_blank_values() -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Branch Grid Filter Project",
        ["fr"],
        ["context"],
    )
    project_id = int(project["project_id"])
    create_bound_variant_with_remarks(
        project_id=project_id,
        business_key="branch.blank",
        source="Blank remark row",
        file_name="",
        translations={"fr": ""},
        remarks={"context": ""},
        branch_refs=[BranchRef.rel_current()],
    )
    create_bound_variant_with_remarks(
        project_id=project_id,
        business_key="branch.other",
        source="Other row",
        file_name="other.xlsx",
        translations={"fr": "Autre"},
        remarks={"context": "filled"},
        branch_refs=[BranchRef.dev("2.5.0")],
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/projects/{project_id}/variants/query",
            json={
                "scope": {"kind": "branch", "branch_ref": "rel/current"},
                "state": "orphan",
                "filters": [
                    {"column": {"kind": "field", "name": "file_name"}, "values": [None]},
                    {"column": {"kind": "translation", "name": "fr"}, "values": [None]},
                    {"column": {"kind": "remark", "name": "context"}, "values": [None]},
                ],
                "page": 1,
                "page_size": 50,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert [row["business_key"] for row in payload["rows"]] == ["branch.blank"]
    assert payload["rows"][0]["state"] == "active"
```

- [ ] **Step 2: Run row endpoint tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py::test_project_variants_query_filters_every_column_family_and_caps_page_size tests/test_variant_api.py::test_project_variants_query_branch_scope_ignores_project_state_and_supports_blank_values
```

Expected: FAIL with 404 or missing route/service behavior.

- [ ] **Step 3: Add rich query SQL helpers**

In `app/services/read_models/repository.py`, import the new filter objects:

```python
from app.schemas import VariantGridColumnRef
from app.services.read_models.grid_filters import GridColumnFilter, GridQuerySpec, filters_excluding_target
```

Add public methods to `ReadModelRepository`:

```python
    def list_grid_variant_rows(
        self,
        spec: GridQuerySpec,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        where_clauses, params = self._grid_where(spec)
        rows = self._select_variant_rows(
            where_clauses,
            params,
            page=spec.page,
            page_size=spec.page_size,
            order_sql=self._grid_order_sql(spec),
            conn=conn,
        )
        total_rows = self._count_variant_rows(where_clauses, params, conn=conn)
        return {
            "rows": rows,
            "total_rows": total_rows,
            "page": spec.page,
            "page_size": spec.page_size,
            "has_next_page": spec.page * spec.page_size < total_rows,
            "total_rows_exact": True,
        }
```

Add `_grid_where`, `_apply_grid_filter`, and helper methods near `_scope_member_where`. Use this exact behavior:

```python
    def _grid_where(self, spec: GridQuerySpec) -> tuple[list[str], list[Any]]:
        where_clauses = [
            "e.project_id = ?",
            "v.trashed_at IS NULL",
        ]
        params: list[Any] = [spec.project_id]
        active_binding_exists = (
            "EXISTS (SELECT 1 FROM scope_bindings active_b WHERE active_b.variant_id = v.variant_id)"
        )
        if spec.scope_selector is None:
            if spec.state == "active":
                where_clauses.append(active_binding_exists)
            elif spec.state == "orphan":
                where_clauses.append(f"NOT {active_binding_exists}")
        else:
            branch_ref = spec.scope_selector.branch_ref
            if branch_ref is None:
                raise ValueError("branch scope selector is required")
            scope_type, scope_value = branch_ref.as_tuple()
            where_clauses.append(
                "EXISTS ("
                "SELECT 1 FROM scope_bindings scope_b "
                "WHERE scope_b.variant_id = v.variant_id "
                "AND scope_b.scope_type = ? "
                "AND scope_b.scope_value = ?"
                ")"
            )
            params.extend([scope_type, scope_value])
        for item in spec.filters:
            self._apply_grid_filter(where_clauses, params, item)
        return where_clauses, params

    def _apply_grid_filter(
        self,
        where_clauses: list[str],
        params: list[Any],
        item: GridColumnFilter,
    ) -> None:
        column = item.column
        if item.text:
            clause, clause_params = self._grid_text_clause(column, item.text)
            where_clauses.append(clause)
            params.extend(clause_params)
        if item.values:
            clause, clause_params = self._grid_values_clause(column, item.values)
            where_clauses.append(clause)
            params.extend(clause_params)
```

Add helper methods for text and exact values. The implementation must use parameter placeholders for all user values. For field columns, map SQL expressions with:

```python
    def _grid_field_expression(self, column_name: str) -> str:
        if column_name == "business_key":
            return "e.business_key"
        if column_name == "file_name":
            return "v.file_name"
        if column_name == "source":
            return "v.source"
        if column_name == "pivot_status":
            return "v.pivot_status"
        if column_name == "state":
            return (
                "CASE WHEN EXISTS (SELECT 1 FROM scope_bindings state_b "
                "WHERE state_b.variant_id = v.variant_id) "
                "THEN 'active' ELSE 'orphan' END"
            )
        raise ValueError(f"unsupported field expression: {column_name}")
```

For translation/remark text:

```python
    def _grid_text_clause(self, column: VariantGridColumnRef, text: str) -> tuple[str, list[Any]]:
        pattern = f"%{text}%"
        if column.kind == "field" and column.name != "branch":
            expr = self._grid_field_expression(column.name)
            return f"LOWER(COALESCE({expr}, '')) LIKE ?", [pattern]
        if column.kind == "field" and column.name == "branch":
            return (
                "EXISTS ("
                "SELECT 1 FROM scope_bindings text_b "
                "WHERE text_b.variant_id = v.variant_id "
                "AND LOWER(text_b.scope_type || '/' || text_b.scope_value) LIKE ?"
                ")",
                [pattern],
            )
        if column.kind == "translation":
            return (
                "EXISTS ("
                "SELECT 1 FROM variant_translations text_vt "
                "WHERE text_vt.variant_id = v.variant_id "
                "AND text_vt.lang = ? "
                "AND LOWER(COALESCE(text_vt.target_text, '')) LIKE ?"
                ")",
                [column.name, pattern],
            )
        if column.kind == "remark":
            return (
                "EXISTS ("
                "SELECT 1 FROM variant_remarks text_vr "
                "WHERE text_vr.variant_id = v.variant_id "
                "AND text_vr.remark_key = ? "
                "AND LOWER(COALESCE(text_vr.remark_value, '')) LIKE ?"
                ")",
                [column.name, pattern],
            )
        raise ValueError(f"unsupported text filter column: {column}")
```

For exact values, implement OR groups:

```python
    def _grid_values_clause(
        self,
        column: VariantGridColumnRef,
        values: tuple[str | None, ...],
    ) -> tuple[str, list[Any]]:
        non_null_values = [value for value in values if value is not None]
        include_blank = any(value is None for value in values)
        pieces: list[str] = []
        params: list[Any] = []
        if column.kind == "field" and column.name != "branch":
            expr = self._grid_field_expression(column.name)
            if non_null_values:
                placeholders = ", ".join("?" for _ in non_null_values)
                pieces.append(f"COALESCE({expr}, '') IN ({placeholders})")
                params.extend(non_null_values)
            if include_blank:
                pieces.append(f"COALESCE({expr}, '') = ''")
            return f"({' OR '.join(pieces)})", params
        if column.kind == "field" and column.name == "branch":
            for branch_ref_value in non_null_values:
                branch_ref = BranchRef.parse(branch_ref_value)
                scope_type, scope_value = branch_ref.as_tuple()
                pieces.append(
                    "EXISTS ("
                    "SELECT 1 FROM scope_bindings value_b "
                    "WHERE value_b.variant_id = v.variant_id "
                    "AND value_b.scope_type = ? "
                    "AND value_b.scope_value = ?"
                    ")"
                )
                params.extend([scope_type, scope_value])
            if include_blank:
                pieces.append(
                    "NOT EXISTS ("
                    "SELECT 1 FROM scope_bindings blank_b "
                    "WHERE blank_b.variant_id = v.variant_id"
                    ")"
                )
            return f"({' OR '.join(pieces)})", params
        if column.kind == "translation":
            return self._grid_child_values_clause(
                table="variant_translations",
                alias="value_vt",
                key_column="lang",
                value_column="target_text",
                key_value=column.name,
                values=values,
            )
        if column.kind == "remark":
            return self._grid_child_values_clause(
                table="variant_remarks",
                alias="value_vr",
                key_column="remark_key",
                value_column="remark_value",
                key_value=column.name,
                values=values,
            )
        raise ValueError(f"unsupported values filter column: {column}")
```

Add `_grid_child_values_clause`:

```python
    def _grid_child_values_clause(
        self,
        *,
        table: str,
        alias: str,
        key_column: str,
        value_column: str,
        key_value: str,
        values: tuple[str | None, ...],
    ) -> tuple[str, list[Any]]:
        non_null_values = [value for value in values if value is not None]
        include_blank = any(value is None for value in values)
        pieces: list[str] = []
        params: list[Any] = []
        if non_null_values:
            placeholders = ", ".join("?" for _ in non_null_values)
            pieces.append(
                "EXISTS ("
                f"SELECT 1 FROM {table} {alias} "
                f"WHERE {alias}.variant_id = v.variant_id "
                f"AND {alias}.{key_column} = ? "
                f"AND COALESCE({alias}.{value_column}, '') IN ({placeholders})"
                ")"
            )
            params.extend([key_value, *non_null_values])
        if include_blank:
            pieces.append(
                "NOT EXISTS ("
                f"SELECT 1 FROM {table} blank_child "
                "WHERE blank_child.variant_id = v.variant_id "
                f"AND blank_child.{key_column} = ? "
                f"AND COALESCE(blank_child.{value_column}, '') <> ''"
                ")"
            )
            params.append(key_value)
        return f"({' OR '.join(pieces)})", params
```

Add ordering:

```python
    def _grid_order_sql(self, spec: GridQuerySpec) -> str:
        if spec.scope_selector is None:
            return "ORDER BY v.updated_at DESC, v.variant_id DESC"
        return "ORDER BY LOWER(e.business_key), v.updated_at DESC, v.variant_id DESC"
```

- [ ] **Step 4: Add dataset facades**

In `app/services/read_models/datasets/live_variants.py`, import `VariantGridQueryRequest`, `GridQuerySpec`, and `build_grid_query`, then add:

```python
    def query(
        self,
        request: VariantGridQueryRequest,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        spec = build_grid_query(project_id, request, projects=self.projects)
        if spec.scope_selector is not None:
            raise ValueError("project live variants query requires project scope")
        payload = self.repository.list_grid_variant_rows(spec)
        return {
            "rows": self.hydrator.live_variants(payload["rows"]),
            "total_rows": payload["total_rows"],
            "page": payload["page"],
            "page_size": payload["page_size"],
            "has_next_page": payload["has_next_page"],
            "total_rows_exact": payload["total_rows_exact"],
        }
```

In `app/services/read_models/datasets/scope_members.py`, import `VariantGridQueryRequest` and `build_grid_query`, then add:

```python
    def query(
        self,
        request: VariantGridQueryRequest,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        spec = build_grid_query(project_id, request, projects=self.projects)
        if spec.scope_selector is None:
            raise ValueError("scope membership query requires branch scope")
        payload = self.repository.list_grid_variant_rows(spec)
        return {
            "scope_ref": str(spec.scope_selector),
            "rows": self.hydrator.scope_members(payload["rows"]),
            "total_rows": payload["total_rows"],
            "page": payload["page"],
            "page_size": payload["page_size"],
            "has_next_page": payload["has_next_page"],
            "total_rows_exact": payload["total_rows_exact"],
        }
```

- [ ] **Step 5: Add route**

In `app/routers/inspection.py`, import:

```python
from app.schemas import (
    EntryVariantsResponse,
    OrphanVariantsResponse,
    ProjectVariantsQueryResponse,
    ProjectVariantsResponse,
    VariantGridQueryRequest,
)
from app.services.read_models.datasets.scope_members import ScopeMembershipDataset
```

Add route after the existing GET variants route:

```python
@router.post("/api/projects/{project_id}/variants/query", response_model=ProjectVariantsQueryResponse)
def project_variants_query(
    project_id: int,
    payload: VariantGridQueryRequest,
) -> ProjectVariantsQueryResponse:
    def run() -> ProjectVariantsQueryResponse:
        if payload.scope.kind == "project":
            result = ProjectLiveVariantsDataset().query(payload, project_id=project_id)
        else:
            result = ScopeMembershipDataset().query(payload, project_id=project_id)
            result.pop("scope_ref", None)
        return ProjectVariantsQueryResponse(**result)

    return handle_errors(run)
```

- [ ] **Step 6: Run Task 2 tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py::test_project_variants_query_filters_every_column_family_and_caps_page_size tests/test_variant_api.py::test_project_variants_query_branch_scope_ignores_project_state_and_supports_blank_values
```

Expected: PASS.

- [ ] **Step 7: Run existing variants route regression**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py::test_project_variants_route_supports_state_filters_and_project_scope tests/test_variant_api.py::test_project_variants_route_supports_branch_filters_search_and_multi_bindings tests/test_variant_api.py::test_project_variants_route_excludes_trashed_variants_and_paginates_stably
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

Run:

```powershell
git add app/routers/inspection.py app/services/read_models/datasets/live_variants.py app/services/read_models/datasets/scope_members.py app/services/read_models/repository.py tests/test_variant_api.py
git commit -m "feat: add variant grid row query"
```

---

### Task 3: Backend Filter Options Endpoint

**Files:**

- Modify `tests/test_variant_api.py`
- Modify `app/services/read_models/repository.py`
- Modify `app/services/read_models/datasets/live_variants.py`
- Modify `app/services/read_models/datasets/scope_members.py`
- Modify `app/routers/inspection.py`

- [ ] **Step 1: Add failing filter options tests**

Add this test near the row query tests:

```python
def test_project_variant_filter_options_return_distinct_values_and_ignore_target_filter() -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Grid Filter Options Project",
        ["fr"],
        ["context"],
    )
    project_id = int(project["project_id"])
    create_bound_variant_with_remarks(
        project_id=project_id,
        business_key="rose.red",
        source="Red rose",
        file_name="flowers.xlsx",
        translations={"fr": "Rose rouge"},
        remarks={"context": "garden"},
        branch_refs=[BranchRef.rel_current()],
    )
    create_bound_variant_with_remarks(
        project_id=project_id,
        business_key="rose.white",
        source="White rose",
        file_name="flowers.xlsx",
        translations={"fr": "Rose blanche"},
        remarks={"context": "vase"},
        branch_refs=[BranchRef.dev("2.5.0")],
    )
    create_bound_variant_with_remarks(
        project_id=project_id,
        business_key="lily.blue",
        source="Blue lily",
        file_name="lilies.xlsx",
        translations={"fr": ""},
        remarks={"context": ""},
        branch_refs=[BranchRef.rel_current()],
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/projects/{project_id}/variants/filter-options",
            json={
                "scope": {"kind": "project"},
                "state": "all",
                "target_column": {"kind": "translation", "name": "fr"},
                "filters": [
                    {"column": {"kind": "field", "name": "source"}, "text": "rose", "values": []},
                    {"column": {"kind": "translation", "name": "fr"}, "text": "", "values": ["Rose rouge"]},
                ],
                "option_search": "rose",
                "limit": 500,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 100
    assert payload["has_more"] is False
    assert [item["value"] for item in payload["values"]] == ["Rose blanche", "Rose rouge"]
    assert [item["label"] for item in payload["values"]] == ["Rose blanche", "Rose rouge"]
```

Add blank and branch option coverage:

```python
def test_project_variant_filter_options_support_blank_and_branch_values() -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Grid Filter Blank Options Project",
        ["fr"],
        ["context"],
    )
    project_id = int(project["project_id"])
    create_bound_variant_with_remarks(
        project_id=project_id,
        business_key="blank.option",
        source="Blank option",
        file_name="",
        translations={"fr": ""},
        remarks={"context": ""},
        branch_refs=[BranchRef.rel_current()],
    )
    create_bound_variant_with_remarks(
        project_id=project_id,
        business_key="dev.option",
        source="Dev option",
        file_name="dev.xlsx",
        translations={"fr": "Dev"},
        remarks={"context": "dev"},
        branch_refs=[BranchRef.dev("2.5.0")],
    )

    with TestClient(app) as client:
        blank_response = client.post(
            f"/api/projects/{project_id}/variants/filter-options",
            json={
                "scope": {"kind": "branch", "branch_ref": "rel/current"},
                "target_column": {"kind": "field", "name": "file_name"},
                "filters": [],
                "limit": 100,
            },
        )
        branch_response = client.post(
            f"/api/projects/{project_id}/variants/filter-options",
            json={
                "scope": {"kind": "project"},
                "state": "all",
                "target_column": {"kind": "field", "name": "branch"},
                "filters": [],
                "limit": 100,
            },
        )

    assert blank_response.status_code == 200
    assert blank_response.json()["values"][0] == {"value": None, "label": "(blank)", "count": None}
    assert branch_response.status_code == 200
    assert [item["value"] for item in branch_response.json()["values"]] == ["dev/2.5.0", "rel/current"]
```

- [ ] **Step 2: Run filter options tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py::test_project_variant_filter_options_return_distinct_values_and_ignore_target_filter tests/test_variant_api.py::test_project_variant_filter_options_support_blank_and_branch_values
```

Expected: FAIL with 404 or missing repository methods.

- [ ] **Step 3: Add repository option selection**

In `app/services/read_models/repository.py`, add:

```python
    def list_grid_filter_options(
        self,
        spec: GridOptionsSpec,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        query_spec = GridQuerySpec(
            project_id=spec.query.project_id,
            scope_selector=spec.query.scope_selector,
            state=spec.query.state,
            filters=filters_excluding_target(spec.query.filters, spec.target_column),
            page=1,
            page_size=spec.query.page_size,
        )
        where_clauses, params = self._grid_where(query_spec)
        value_sql, value_params = self._grid_option_value_sql(spec.target_column)
        where_sql = " AND ".join(where_clauses)
        option_params = [*value_params, *params]
        search_sql = ""
        if spec.option_search:
            search_sql = "WHERE LOWER(COALESCE(value, '')) LIKE ?"
            option_params.append(f"%{spec.option_search}%")
        option_params.append(spec.limit + 1)
        query = f"""
            SELECT DISTINCT value
            FROM (
                SELECT {value_sql} AS value
                FROM variants v
                JOIN entries e ON e.entry_id = v.entry_id
                {self._grid_option_join_sql(spec.target_column)}
                WHERE {where_sql}
            )
            {search_sql}
            ORDER BY
                CASE WHEN value IS NULL THEN 0 ELSE 1 END,
                LOWER(COALESCE(value, ''))
            LIMIT ?
        """
        if conn is not None:
            rows = conn.execute(query, option_params).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(query, option_params).fetchall()
        raw_values = [row["value"] for row in rows]
        limited_values = raw_values[: spec.limit]
        return {
            "values": [
                {
                    "value": value,
                    "label": "(blank)" if value is None else str(value),
                    "count": None,
                }
                for value in limited_values
            ],
            "limit": spec.limit,
            "has_more": len(raw_values) > spec.limit,
        }
```

Import `GridOptionsSpec` from `grid_filters`.

Add option SQL helpers:

```python
    def _grid_option_join_sql(self, column: VariantGridColumnRef) -> str:
        if column.kind == "field" and column.name == "branch":
            return "LEFT JOIN scope_bindings option_b ON option_b.variant_id = v.variant_id"
        if column.kind == "translation":
            return (
                "LEFT JOIN variant_translations option_vt "
                "ON option_vt.variant_id = v.variant_id AND option_vt.lang = ?"
            )
        if column.kind == "remark":
            return (
                "LEFT JOIN variant_remarks option_vr "
                "ON option_vr.variant_id = v.variant_id AND option_vr.remark_key = ?"
            )
        return ""

    def _grid_option_value_sql(self, column: VariantGridColumnRef) -> tuple[str, list[Any]]:
        if column.kind == "field":
            if column.name == "branch":
                return (
                    "CASE WHEN option_b.variant_id IS NULL "
                    "THEN NULL ELSE option_b.scope_type || '/' || option_b.scope_value END",
                    [],
                )
            expr = self._grid_field_expression(column.name)
            return f"NULLIF(COALESCE({expr}, ''), '')", []
        if column.kind == "translation":
            return "NULLIF(COALESCE(option_vt.target_text, ''), '')", [column.name]
        if column.kind == "remark":
            return "NULLIF(COALESCE(option_vr.remark_value, ''), '')", [column.name]
        raise ValueError(f"unsupported option column: {column}")
```

- [ ] **Step 4: Add dataset option facades**

In `app/services/read_models/datasets/live_variants.py`, import `VariantGridFilterRequest` and `build_grid_options`, then add:

```python
    def filter_options(
        self,
        request: VariantGridFilterRequest,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        spec = build_grid_options(project_id, request, projects=self.projects)
        if spec.query.scope_selector is not None:
            raise ValueError("project live variant filter options require project scope")
        return self.repository.list_grid_filter_options(spec)
```

In `app/services/read_models/datasets/scope_members.py`, import `VariantGridFilterRequest` and `build_grid_options`, then add:

```python
    def filter_options(
        self,
        request: VariantGridFilterRequest,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        spec = build_grid_options(project_id, request, projects=self.projects)
        if spec.query.scope_selector is None:
            raise ValueError("scope membership filter options require branch scope")
        return self.repository.list_grid_filter_options(spec)
```

- [ ] **Step 5: Add options route**

In `app/routers/inspection.py`, import:

```python
from app.schemas import VariantFilterOptionsResponse, VariantGridFilterRequest
```

Add after `project_variants_query`:

```python
@router.post("/api/projects/{project_id}/variants/filter-options", response_model=VariantFilterOptionsResponse)
def project_variant_filter_options(
    project_id: int,
    payload: VariantGridFilterRequest,
) -> VariantFilterOptionsResponse:
    def run() -> VariantFilterOptionsResponse:
        if payload.scope.kind == "project":
            result = ProjectLiveVariantsDataset().filter_options(payload, project_id=project_id)
        else:
            result = ScopeMembershipDataset().filter_options(payload, project_id=project_id)
        return VariantFilterOptionsResponse(**result)

    return handle_errors(run)
```

- [ ] **Step 6: Run Task 3 tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py::test_project_variant_filter_options_return_distinct_values_and_ignore_target_filter tests/test_variant_api.py::test_project_variant_filter_options_support_blank_and_branch_values
```

Expected: PASS.

- [ ] **Step 7: Run backend route suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py tests/test_bulk_seed.py
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```powershell
git add app/routers/inspection.py app/services/read_models/datasets/live_variants.py app/services/read_models/datasets/scope_members.py app/services/read_models/repository.py tests/test_variant_api.py
git commit -m "feat: add variant grid filter options"
```

---

### Task 4: Frontend API Types And Browse Query Migration

**Files:**

- Modify `frontend/src/domains/variants/types.ts`
- Modify `frontend/src/domains/variants/api.ts`
- Create `frontend/src/shared/ui/variantGridFilters.ts`
- Modify `frontend/src/pages/workspace/WorkspacePage.tsx`
- Modify `frontend/src/pages/release/ReleasePage.tsx`
- Modify `frontend/src/pages/dev/BranchDetail.tsx`
- Modify `tests/e2e/product-app.spec.js`

- [ ] **Step 1: Add failing e2e request coverage for POST row query**

In `tests/e2e/product-app.spec.js`, update the test named `"Workspace reflects state and branch filters in URL and API params"` so it routes POST requests:

```javascript
  const variantRequests = [];
  await page.route("**/api/projects/1/variants/query", async (route) => {
    const payload = route.request().postDataJSON();
    variantRequests.push(payload);
    await route.continue();
  });
```

Update assertions in that test:

```javascript
  await expect.poll(() => variantRequests.some((item) => item.state === "all")).toBeTruthy();

  await page.getByLabel(/Branch:/).selectOption("rel/current");
  await expect.poll(() => new URL(page.url()).searchParams.get("branch")).toBe("rel/current");
  await expect
    .poll(() => variantRequests.some((item) => item.scope?.branch_ref === "rel/current"))
    .toBeTruthy();
  await expect
    .poll(() => variantRequests.some((item) => item.page_size === 50))
    .toBeTruthy();
```

In `"normalizes stale branch params before branch-scoped pages query data"`, change the route capture to:

```javascript
  await page.route("**/api/projects/1/variants/query", async (route) => {
    const payload = route.request().postDataJSON();
    variantRequests.push(payload.scope?.branch_ref ?? null);
    await route.continue();
  });
```

Update its final assertion:

```javascript
    variantRequests.includes("dev/9.9.9"),
```

- [ ] **Step 2: Run e2e test and verify RED**

Run:

```powershell
npm run test:e2e -- tests/e2e/product-app.spec.js
```

Expected: FAIL because the frontend still calls `GET /variants`.

- [ ] **Step 3: Add frontend types**

In `frontend/src/domains/variants/types.ts`, add:

```typescript
export type VariantGridColumnRef = {
  kind: "field" | "translation" | "remark";
  name: string;
};

export type VariantGridScope =
  | { kind: "project" }
  | { kind: "branch"; branch_ref: string };

export type VariantGridColumnFilter = {
  column: VariantGridColumnRef;
  text?: string | null;
  values?: Array<string | null>;
};

export type VariantGridQueryRequest = {
  scope: VariantGridScope;
  state?: "active" | "orphan" | "all";
  filters?: VariantGridColumnFilter[];
  page?: number;
  page_size?: number;
};

export type ProjectVariantsQueryResponse = ProjectVariantsResponse & {
  has_next_page: boolean;
  total_rows_exact: boolean;
};

export type VariantFilterOptionValue = {
  value: string | null;
  label: string;
  count: number | null;
};

export type VariantFilterOptionsRequest = VariantGridQueryRequest & {
  target_column: VariantGridColumnRef;
  option_search?: string | null;
  limit?: number;
};

export type VariantFilterOptionsResponse = {
  values: VariantFilterOptionValue[];
  limit: number;
  has_more: boolean;
};
```

- [ ] **Step 4: Add frontend API helpers**

In `frontend/src/domains/variants/api.ts`, import the new types and add:

```typescript
export function queryProjectVariants(
  projectId: number,
  payload: VariantGridQueryRequest,
) {
  return fetchJson<ProjectVariantsQueryResponse>(
    `/api/projects/${projectId}/variants/query`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function getProjectVariantFilterOptions(
  projectId: number,
  payload: VariantFilterOptionsRequest,
) {
  return fetchJson<VariantFilterOptionsResponse>(
    `/api/projects/${projectId}/variants/filter-options`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
```

- [ ] **Step 5: Add grid filter helpers**

Create `frontend/src/shared/ui/variantGridFilters.ts`:

```typescript
import type {
  VariantGridColumnFilter,
  VariantGridColumnRef,
} from "@/domains/variants/types";

export type VariantGridColumnFilterState = {
  text: string;
  values: Array<string | null>;
};

export type VariantGridFilterState = Record<string, VariantGridColumnFilterState>;

export function columnKey(column: VariantGridColumnRef): string {
  return `${column.kind}:${column.name}`;
}

export function parseColumnKey(value: string): VariantGridColumnRef | null {
  const index = value.indexOf(":");
  if (index <= 0) return null;
  const kind = value.slice(0, index);
  const name = value.slice(index + 1);
  if ((kind !== "field" && kind !== "translation" && kind !== "remark") || !name) {
    return null;
  }
  return { kind, name };
}

export function toApiFilters(filters: VariantGridFilterState): VariantGridColumnFilter[] {
  return Object.entries(filters).flatMap(([key, filter]) => {
    const column = parseColumnKey(key);
    if (!column) return [];
    const text = filter.text.trim();
    const values = filter.values;
    if (!text && values.length === 0) return [];
    return [{ column, text, values }];
  });
}

export function hasAnyFilter(filters: VariantGridFilterState): boolean {
  return toApiFilters(filters).length > 0;
}

export function encodeGridFilters(filters: VariantGridFilterState): string | null {
  const entries = Object.entries(filters)
    .map(([key, filter]) => [key, { text: filter.text.trim(), values: filter.values }] as const)
    .filter(([, filter]) => filter.text || filter.values.length > 0);
  return entries.length > 0 ? JSON.stringify(Object.fromEntries(entries)) : null;
}

export function decodeGridFilters(value: string | null): VariantGridFilterState {
  if (!value) return {};
  try {
    const parsed = JSON.parse(value) as Record<string, VariantGridColumnFilterState>;
    const result: VariantGridFilterState = {};
    for (const [key, filter] of Object.entries(parsed)) {
      if (!parseColumnKey(key)) continue;
      result[key] = {
        text: typeof filter.text === "string" ? filter.text : "",
        values: Array.isArray(filter.values)
          ? filter.values.filter((item): item is string | null => item === null || typeof item === "string")
          : [],
      };
    }
    return result;
  } catch {
    return {};
  }
}
```

- [ ] **Step 6: Migrate browse pages to POST rows and 50-row pages**

In `WorkspacePage.tsx`:

- replace `getProjectVariants` import with `queryProjectVariants`;
- import `decodeGridFilters`, `encodeGridFilters`, and `toApiFilters`;
- set `const pageSize = 50;`;
- derive `gridFilters` from `searchParams.get("grid_filters")`;
- build payload:

```typescript
  const gridFilters = decodeGridFilters(searchParams.get("grid_filters"));
  const deferredGridFilters = useDeferredValue(gridFilters);
  const pageSize = 50;
  const params = {
    scope: branchFilter
      ? { kind: "branch" as const, branch_ref: branchFilter }
      : { kind: "project" as const },
    state: stateFilter,
    filters: toApiFilters(deferredGridFilters),
    page,
    page_size: pageSize,
  };
```

- use query:

```typescript
  const query = useQuery({
    queryKey: queryKeys.projectVariants(projectId, params),
    queryFn: () => queryProjectVariants(projectId, params),
  });
```

- replace `columnFilters` usage for text filters with `gridFilters`;
- keep `branch` in its existing toolbar select.
- pass `branchFilter={branchFilter ?? ""}` and `onBranchFilterChange={(value) => handleColumnFilter("branch", value)}` to `VariantGrid`.

Add handlers:

```typescript
  function handleGridFiltersChange(nextFilters: VariantGridFilterState) {
    setSearchParams(
      (current) => applySearchPatch(current, {
        grid_filters: encodeGridFilters(nextFilters),
        page: null,
      }),
      { replace: false },
    );
  }
```

In `ReleasePage.tsx` and `BranchDetail.tsx`:

- replace `getBranchRows` with `queryProjectVariants`;
- use `useState<VariantGridFilterState>({})`;
- use `pageSize = 50`;
- build branch-scope payload:

```typescript
  const browseParams = {
    scope: { kind: "branch" as const, branch_ref: branchRef },
    filters: toApiFilters(deferredFilters),
    page,
    page_size: pageSize,
  };
```

Use `queryProjectVariants(projectId, browseParams)`.

- [ ] **Step 7: Temporarily pass no-op filter UI props**

Update `VariantGridProps` in `VariantGrid.tsx` to accept new filter state names while preserving UI until Task 5:

```typescript
import type {
  VariantFilterOptionsRequest,
  VariantFilterOptionsResponse,
  VariantGridColumnRef,
} from "@/domains/variants/types";
import type { VariantGridFilterState } from "@/shared/ui/variantGridFilters";
```

Replace old text filter props:

```typescript
  filters: VariantGridFilterState;
  onFiltersChange: (filters: VariantGridFilterState) => void;
  branchFilter?: string;
  onBranchFilterChange?: (value: string) => void;
  loadFilterOptions: (
    targetColumn: VariantGridColumnRef,
    optionSearch: string,
  ) => Promise<VariantFilterOptionsResponse>;
```

For this task only, keep headers as plain names and do not render popovers yet. Add a toolbar button:

```tsx
        <button type="button" className={styles.clearButton} onClick={() => onFiltersChange({})}>
          Clear filters
        </button>
```

Disable it when `Object.keys(filters).length === 0`.

Update the branch toolbar select to use the new branch props:

```tsx
        {branchOptions && (
          <label className={styles.toolbarItem}>
            Branch:
            <select
              value={branchFilter ?? ""}
              onChange={(e) => onBranchFilterChange?.(e.target.value)}
            >
              <option value="">All branches</option>
              {branchOptions.map((branchRef) => (
                <option key={branchRef} value={branchRef}>{branchRef}</option>
              ))}
            </select>
          </label>
        )}
```

- [ ] **Step 8: Wire filter option loader props**

In each page, import `getProjectVariantFilterOptions` and pass:

```typescript
      loadFilterOptions={(targetColumn, optionSearch) =>
        getProjectVariantFilterOptions(projectId, {
          ...params,
          target_column: targetColumn,
          option_search: optionSearch,
          limit: 100,
        })
      }
```

For Release and Dev, use `browseParams` instead of `params`.

- [ ] **Step 9: Run build and e2e test and verify GREEN**

Run:

```powershell
npm run build:app
npm run test:e2e -- tests/e2e/product-app.spec.js
```

Expected: build PASS and the updated e2e tests PASS.

- [ ] **Step 10: Commit Task 4**

Run:

```powershell
git add frontend/src/domains/variants/api.ts frontend/src/domains/variants/types.ts frontend/src/pages/dev/BranchDetail.tsx frontend/src/pages/release/ReleasePage.tsx frontend/src/pages/workspace/WorkspacePage.tsx frontend/src/shared/ui/VariantGrid.tsx frontend/src/shared/ui/variantGridFilters.ts tests/e2e/product-app.spec.js
git commit -m "feat: query variant grids through rich filter api"
```

---

### Task 5: Header Filter Popover UI

**Files:**

- Modify `frontend/src/shared/ui/VariantGrid.tsx`
- Modify `frontend/src/shared/ui/VariantGrid.module.css`
- Modify `tests/e2e/product-app.spec.js`

- [ ] **Step 1: Add failing e2e coverage for header filter UI**

Append this test after the Workspace filter URL test in `tests/e2e/product-app.spec.js`:

```javascript
test("Workspace applies source header filter with explicit apply", async ({
  page,
}) => {
  const queryRequests = [];
  const optionsRequests = [];

  await page.route("**/api/projects/1/variants/query", async (route) => {
    const payload = route.request().postDataJSON();
    queryRequests.push(payload);
    await route.continue();
  });
  await page.route("**/api/projects/1/variants/filter-options", async (route) => {
    const payload = route.request().postDataJSON();
    optionsRequests.push(payload);
    await route.fulfill({
      json: {
        values: [
          { value: "Welcome source", label: "Welcome source", count: null },
        ],
        limit: 100,
        has_more: true,
      },
    });
  });

  await page.goto("/app/workspace?project=1&lang=fr&state=all");
  await page.getByRole("button", { name: "Filter source" }).click();
  await expect(page.getByText("Showing first 100 values")).toBeVisible();
  await page.getByLabel("Search source").fill("welcome");
  await expect.poll(() => queryRequests.some((item) =>
    (item.filters || []).some((filter) => filter.text === "welcome")
  )).toBeFalsy();
  await page.getByRole("button", { name: "Apply source filter" }).click();

  await expect.poll(() => queryRequests.some((item) =>
    (item.filters || []).some((filter) =>
      filter.column.kind === "field" &&
      filter.column.name === "source" &&
      filter.text === "welcome"
    )
  )).toBeTruthy();
  await expect
    .poll(() => optionsRequests.some((item) => item.target_column?.name === "source"))
    .toBeTruthy();
});
```

- [ ] **Step 2: Run e2e test and verify RED**

Run:

```powershell
npm run test:e2e -- tests/e2e/product-app.spec.js
```

Expected: FAIL because header filter buttons/popovers do not exist.

- [ ] **Step 3: Add column filter components**

In `VariantGrid.tsx`, import:

```typescript
import { useEffect, useMemo, useState } from "react";
import { columnKey, hasAnyFilter } from "@/shared/ui/variantGridFilters";
```

Add helpers above `VariantGrid`:

```typescript
function optionValueKey(value: string | null): string {
  return value === null ? "__blank__" : value;
}

function toggleOption(
  values: Array<string | null>,
  value: string | null,
): Array<string | null> {
  const key = optionValueKey(value);
  const exists = values.some((item) => optionValueKey(item) === key);
  return exists
    ? values.filter((item) => optionValueKey(item) !== key)
    : [...values, value];
}
```

Add `HeaderFilterButton` component:

```tsx
function HeaderFilterButton(props: {
  label: string;
  column: VariantGridColumnRef;
  filters: VariantGridFilterState;
  activeColumnKey: string | null;
  setActiveColumnKey: (key: string | null) => void;
  onFiltersChange: (filters: VariantGridFilterState) => void;
  loadFilterOptions: (
    targetColumn: VariantGridColumnRef,
    optionSearch: string,
  ) => Promise<VariantFilterOptionsResponse>;
}) {
  const key = columnKey(props.column);
  const committed = props.filters[key] ?? { text: "", values: [] };
  const isOpen = props.activeColumnKey === key;
  const isActive = committed.text.trim() !== "" || committed.values.length > 0;

  return (
    <button
      type="button"
      className={`${styles.filterButton} ${isActive ? styles.filterButtonActive : ""}`}
      aria-label={`Filter ${props.label}`}
      title={`Filter ${props.label}`}
      onClick={(event) => {
        event.stopPropagation();
        props.setActiveColumnKey(isOpen ? null : key);
      }}
    >
      ▾
    </button>
  );
}
```

Add `HeaderFilterPopover` component that renders when `activeColumnKey` is open:

```tsx
function HeaderFilterPopover(props: {
  label: string;
  column: VariantGridColumnRef;
  filters: VariantGridFilterState;
  onFiltersChange: (filters: VariantGridFilterState) => void;
  onClose: () => void;
  loadFilterOptions: (
    targetColumn: VariantGridColumnRef,
    optionSearch: string,
  ) => Promise<VariantFilterOptionsResponse>;
}) {
  const key = columnKey(props.column);
  const committed = props.filters[key] ?? { text: "", values: [] };
  const [draftText, setDraftText] = useState(committed.text);
  const [draftValues, setDraftValues] = useState<Array<string | null>>(committed.values);
  const [optionSearch, setOptionSearch] = useState("");
      const [options, setOptions] = useState<VariantFilterOptionsResponse | null>(null);
      const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    props.loadFilterOptions(props.column, optionSearch)
      .then((data) => {
        if (!cancelled) {
          setOptions(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [optionSearch, props.column.kind, props.column.name]);

  function apply() {
    const next = { ...props.filters };
    const value = { text: draftText.trim(), values: draftValues };
    if (!value.text && value.values.length === 0) {
      delete next[key];
    } else {
      next[key] = value;
    }
    props.onFiltersChange(next);
    props.onClose();
  }

  function clearColumn() {
    const next = { ...props.filters };
    delete next[key];
    props.onFiltersChange(next);
    props.onClose();
  }

  return (
    <div className={styles.filterPopover} onClick={(event) => event.stopPropagation()}>
      <label className={styles.filterLabel}>
        <span>Search</span>
        <input
          aria-label={`Search ${props.label}`}
          value={draftText}
          onChange={(event) => setDraftText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") apply();
          }}
        />
      </label>
      <label className={styles.filterLabel}>
        <span>Find values</span>
        <input
          aria-label={`Find ${props.label} values`}
          value={optionSearch}
          onChange={(event) => setOptionSearch(event.target.value)}
        />
      </label>
      <div className={styles.optionList}>
        {error ? <span className={styles.optionMeta}>{error}</span> : null}
        {options?.values.map((option) => (
          <label key={optionValueKey(option.value)} className={styles.optionItem} title={option.label}>
            <input
              type="checkbox"
              checked={draftValues.some((item) => optionValueKey(item) === optionValueKey(option.value))}
              onChange={() => setDraftValues((current) => toggleOption(current, option.value))}
            />
            <span>{option.label}</span>
          </label>
        ))}
        {options?.has_more ? <span className={styles.optionMeta}>Showing first 100 values</span> : null}
      </div>
      <div className={styles.filterActions}>
        <button type="button" onClick={clearColumn}>Clear column</button>
        <button type="button" onClick={apply} aria-label={`Apply ${props.label} filter`}>Apply</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Render filter headers for all visible columns**

In `VariantGrid`, add:

```typescript
  const [activeColumnKey, setActiveColumnKey] = useState<string | null>(null);
```

Create a helper inside `VariantGrid` before `columns`:

```tsx
  function renderFilterableHeader(label: string, column: VariantGridColumnRef) {
    const key = columnKey(column);
    return (
      <div className={styles.headerCell}>
        <span>{label}</span>
        <HeaderFilterButton
          label={label}
          column={column}
          filters={filters}
          activeColumnKey={activeColumnKey}
          setActiveColumnKey={setActiveColumnKey}
          onFiltersChange={onFiltersChange}
          loadFilterOptions={loadFilterOptions}
        />
        {activeColumnKey === key ? (
          <HeaderFilterPopover
            label={label}
            column={column}
            filters={filters}
            onFiltersChange={onFiltersChange}
            onClose={() => setActiveColumnKey(null)}
            loadFilterOptions={loadFilterOptions}
          />
        ) : null}
      </div>
    );
  }
```

Use it for these columns:

```tsx
renderHeaderCell: () => renderFilterableHeader("business_key", { kind: "field", name: "business_key" })
renderHeaderCell: () => renderFilterableHeader("file_name", { kind: "field", name: "file_name" })
renderHeaderCell: () => renderFilterableHeader("source", { kind: "field", name: "source" })
renderHeaderCell: () => renderFilterableHeader(lang, { kind: "translation", name: lang })
renderHeaderCell: () => renderFilterableHeader(key, { kind: "remark", name: key })
renderHeaderCell: () => renderFilterableHeader("pivot_status", { kind: "field", name: "pivot_status" })
renderHeaderCell: () => renderFilterableHeader("branch", { kind: "field", name: "branch" })
renderHeaderCell: () => renderFilterableHeader("state", { kind: "field", name: "state" })
```

Remove the old `HeaderFilter` input component.

- [ ] **Step 5: Add CSS**

In `VariantGrid.module.css`, replace `.headerFilter` rules with:

```css
.filterButton {
  inline-size: 24px;
  block-size: 24px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
}

.filterButtonActive {
  border-color: var(--accent);
  color: var(--accent);
}

.filterPopover {
  position: absolute;
  z-index: 20;
  inset-block-start: calc(100% - 2px);
  inset-inline-start: 0;
  display: grid;
  gap: 8px;
  inline-size: 260px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.16);
}

.filterLabel {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}

.filterLabel input {
  inline-size: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text);
}

.optionList {
  display: grid;
  gap: 4px;
  max-block-size: 220px;
  overflow: auto;
}

.optionItem {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text);
}

.optionItem span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.optionMeta {
  font-size: 12px;
  color: var(--muted);
}

.filterActions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}

.filterActions button,
.clearButton {
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text);
  font-size: 12px;
  cursor: pointer;
}

.filterActions button:last-child {
  border-color: var(--accent);
  color: var(--accent);
}

.clearButton:disabled {
  opacity: 0.45;
  cursor: default;
}
```

Ensure `.headerCell` has:

```css
  position: relative;
  grid-template-columns: minmax(0, 1fr) 24px;
  align-items: center;
```

- [ ] **Step 6: Run build and e2e test and verify GREEN**

Run:

```powershell
npm run build:app
npm run test:e2e -- tests/e2e/product-app.spec.js
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

Run:

```powershell
git add frontend/src/shared/ui/VariantGrid.tsx frontend/src/shared/ui/VariantGrid.module.css tests/e2e/product-app.spec.js
git commit -m "feat: add variant grid header filter UI"
```

---

### Task 6: Runtime Docs And Final Verification

**Files:**

- Modify `docs/contracts.md`
- Modify `docs/system.md`
- Modify `design/2026-05-07-variant-grid-filter-design.md` only if implementation intentionally differs from the approved design.

- [ ] **Step 1: Update contracts docs**

In `docs/contracts.md`, update "Variants workspace query" to include:

```markdown
Rich variant grid query:

- `POST /api/projects/{project_id}/variants/query` accepts a JSON body with `scope`, optional `state`, `filters`, `page`, and `page_size`
- `scope.kind = project` returns project-wide live variants, excluding trashed rows; `state` supports `active`, `orphan`, and `all`
- `scope.kind = branch` requires `branch_ref` and returns rows bound to that branch; branch-scope row queries ignore project `state`
- `filters[]` accepts a typed `column` plus optional `text` and `values[]`
- supported column refs are `field:business_key`, `field:file_name`, `field:source`, `field:branch`, `field:state`, `field:pivot_status`, `translation:<lang>`, and `remark:<key>`
- `text` is case-insensitive contains; `values[]` is exact matching; same-column text and values combine with AND, and different columns combine with AND
- `page_size` defaults to 50 and is capped at 50
- response rows reuse `ProjectVariantRow` and add `has_next_page` plus `total_rows_exact`

Rich variant grid filter options:

- `POST /api/projects/{project_id}/variants/filter-options` accepts the same scope and filters plus `target_column`, optional `option_search`, and `limit`
- the route returns distinct values for `target_column`, applies other column filters, ignores filters for `target_column`, defaults `limit` to 100, and caps it at 100
- blank or missing values are represented as JSON `null` and displayed by `/app` as `(blank)`
```

Add both routes to the HTTP Routes "Inspection reads" list:

```markdown
- `POST /api/projects/{project_id}/variants/query`
- `POST /api/projects/{project_id}/variants/filter-options`
```

In "Frontend And Backend Contract", add:

```markdown
- `/app` uses the rich variant grid POST APIs for Workspace, Release browse, and Dev browse filtering; legacy GET row APIs remain available for simple reads
- variant grid row pages use 50 rows; filter option lists show at most the first 100 distinct values
```

- [ ] **Step 2: Update system docs**

In `docs/system.md`, change:

```markdown
Current schema version: `variant-v12`
```

to:

```markdown
Current schema version: `variant-v13`
```

In the read-model data flow section, add:

```markdown
5. Rich grid filters are evaluated in SQL before hydration. The row query pages variant ids first, hydrates only the selected page, and uses translation/remark lookup indexes for column filters and option lists.
```

- [ ] **Step 3: Run focused backend verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py tests/test_bulk_seed.py
```

Expected: PASS.

- [ ] **Step 4: Run frontend verification**

Run:

```powershell
npm run build:app
npm run test:e2e
```

Expected: PASS.

- [ ] **Step 5: Run docs validation**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected: PASS for files touched by this implementation. If the validator still reports existing archive/design link errors unrelated to this work, include the full failure summary in the final report and do not patch archive files unless the user asks.

- [ ] **Step 6: Review diff against design**

Run:

```powershell
git diff --stat HEAD
git diff -- docs/contracts.md docs/system.md app frontend tests
```

Confirm:

- New POST APIs match the design.
- Existing GET APIs still exist.
- Grid page size is 50.
- Option limit is 100.
- Workspace branch filtering changes POST scope to branch scope.
- Release and Dev browse pages use branch scope.
- No removed route or old-data compatibility behavior was reintroduced.

- [ ] **Step 7: Commit Task 6**

Run:

```powershell
git add docs/contracts.md docs/system.md
git commit -m "docs: document variant grid filters"
```

---

## Subagent Execution Notes

- Execute tasks sequentially. Backend tasks touch overlapping files and must not run in parallel.
- Each implementer must follow TDD:
  1. add the failing test;
  2. run it and capture the expected failure;
  3. implement the minimum behavior;
  4. rerun focused tests;
  5. commit.
- Each worker must not revert changes made by other workers.
- After each implementation task, run a spec-compliance review before code-quality review.
- The final review must check the full implementation against:
  - `design/2026-05-07-variant-grid-filter-design.md`
  - this implementation plan
  - `AGENTS.md`
  - `code_review.md`
