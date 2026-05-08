# Variant Grid Filter Select All Invert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add WPS-like `Select All` and `Invert` controls to variant grid header filters without fetching every distinct value into the browser.

**Architecture:** Extend grid column filters from a selected-values-only model to a value selection model: `all`, `include`, or `exclude`, with optional `value_search` describing the candidate universe for `Select All`. Backend SQL applies the selection mode directly against the filtered project or branch scope. Filter option loading remains capped at 100 values and sorted by name only; count sorting is intentionally out of scope.

**Tech Stack:** FastAPI, Pydantic, SQLite, React, TypeScript, react-data-grid, Playwright.

---

## File Structure

- `app/schemas.py`: add `value_mode` and `value_search` to `VariantGridColumnFilter`.
- `app/services/read_models/grid_filters.py`: validate and normalize the new filter fields.
- `app/services/read_models/repository.py`: apply `all/include/exclude` value semantics in SQL row queries while keeping option list loading capped at 100.
- `frontend/src/domains/variants/types.ts`: mirror the API filter shape in TypeScript.
- `frontend/src/shared/ui/variantGridFilters.ts`: encode/decode/prune the richer filter state for URLs and API payloads.
- `frontend/src/shared/ui/VariantGrid.tsx`: add `Select All` and `Invert` controls to the filter popover.
- `frontend/src/shared/ui/VariantGrid.module.css`: style the new controls in the compact WPS-like popover.
- `tests/test_variant_api.py`: backend regression coverage for `include`, `exclude`, and `all + value_search`.
- `tests/e2e/product-app.spec.js`: browser coverage for `Select All` and `Invert`.
- `docs/contracts.md`: document the updated filter contract.
- `app/static/product-app/*`: rebuilt product app assets.

---

### Task 1: Backend Filter Selection Semantics

**Files:**
- Modify: `app/schemas.py`
- Modify: `app/services/read_models/grid_filters.py`
- Modify: `app/services/read_models/repository.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Write failing API tests**

Add tests near the existing variant grid filter tests in `tests/test_variant_api.py`:

```python
def test_variant_grid_filter_include_and_exclude_values(client):
    project_id = _create_project(client)
    _seed_project_variants(
        client,
        project_id,
        [
            ["k.one", "One source", "Un"],
            ["k.two", "Two source", "Deux"],
            ["k.three", "Three source", "Trois"],
        ],
    )

    include_response = client.post(
        f"/api/projects/{project_id}/variants/query",
        json={
            "scope": {"kind": "project"},
            "state": "all",
            "filters": [
                {
                    "column": {"kind": "field", "name": "source"},
                    "value_mode": "include",
                    "values": ["One source", "Three source"],
                }
            ],
        },
    )
    assert include_response.status_code == 200
    assert [row["business_key"] for row in include_response.json()["rows"]] == ["k.one", "k.three"]

    exclude_response = client.post(
        f"/api/projects/{project_id}/variants/query",
        json={
            "scope": {"kind": "project"},
            "state": "all",
            "filters": [
                {
                    "column": {"kind": "field", "name": "source"},
                    "value_mode": "exclude",
                    "values": ["Two source"],
                }
            ],
        },
    )
    assert exclude_response.status_code == 200
    assert [row["business_key"] for row in exclude_response.json()["rows"]] == ["k.one", "k.three"]
```

Add:

```python
def test_variant_grid_filter_all_mode_uses_value_search_universe(client):
    project_id = _create_project(client)
    _seed_project_variants(
        client,
        project_id,
        [
            ["rose.red", "Red rose", "Rose rouge"],
            ["rose.white", "White rose", "Rose blanche"],
            ["tree.oak", "Oak tree", "Chene"],
        ],
    )

    response = client.post(
        f"/api/projects/{project_id}/variants/query",
        json={
            "scope": {"kind": "project"},
            "state": "all",
            "filters": [
                {
                    "column": {"kind": "field", "name": "source"},
                    "value_mode": "all",
                    "value_search": "rose",
                    "values": [],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert [row["business_key"] for row in response.json()["rows"]] == ["rose.red", "rose.white"]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py::test_variant_grid_filter_include_and_exclude_values tests/test_variant_api.py::test_variant_grid_filter_all_mode_uses_value_search_universe
```

Expected: tests fail because `value_mode` and `value_search` are ignored or rejected.

- [ ] **Step 3: Implement backend fields and SQL**

In `app/schemas.py`, change `VariantGridColumnFilter` to include:

```python
    value_mode: Literal["all", "include", "exclude"] = "include"
    value_search: str | None = None
```

In `app/services/read_models/grid_filters.py`, extend `GridColumnFilter`:

```python
@dataclass(frozen=True)
class GridColumnFilter:
    column: VariantGridColumnRef
    text: str
    values: tuple[str | None, ...]
    value_mode: str
    value_search: str
```

Normalize in `_validated_filter`:

```python
value_mode = item.value_mode
value_search = normalize_non_content_value(item.value_search).lower()
```

In `app/services/read_models/repository.py`, update the column-filter SQL builder so:

- text search still applies as row contains filtering.
- `value_mode == "include"` applies `value IN (...)` or blank matching for the listed values.
- `value_mode == "exclude"` applies the negation of the listed values.
- `value_mode == "all"` applies no exact-value filter unless `value_search` is present; with `value_search`, apply `LOWER(COALESCE(value, '')) LIKE ?`.

- [ ] **Step 4: Run tests and verify GREEN**

Run the same focused backend command. Expected: both tests pass.

- [ ] **Step 5: Run existing API regression**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py tests/test_bulk_seed.py
```

Expected: pass.

---

### Task 2: Frontend Filter State And Popover Controls

**Files:**
- Modify: `frontend/src/domains/variants/types.ts`
- Modify: `frontend/src/shared/ui/variantGridFilters.ts`
- Modify: `frontend/src/shared/ui/VariantGrid.tsx`
- Modify: `frontend/src/shared/ui/VariantGrid.module.css`
- Test: `tests/e2e/product-app.spec.js`

- [ ] **Step 1: Write failing e2e coverage**

Add a test near the existing workspace header filter tests:

```javascript
test("Workspace header filter supports select all and invert semantics", async ({
  page,
}) => {
  const queryRequests = [];

  await page.route("**/api/projects/1/variants/query", async (route) => {
    queryRequests.push(route.request().postDataJSON());
    await route.continue();
  });
  await page.route("**/api/projects/1/variants/filter-options", async (route) => {
    await route.fulfill({
      json: {
        values: [
          { value: "First dev source", label: "First dev source", count: null },
          { value: "Second dev source", label: "Second dev source", count: null },
        ],
        limit: 100,
        has_more: false,
      },
    });
  });

  await page.goto("/app/workspace?project=1&lang=fr&state=all");
  await page.getByRole("button", { name: "Filter source" }).click();
  await page.getByLabel("Find source values").fill("dev");
  await page.getByRole("button", { name: "Select all source values" }).click();
  await page.getByRole("button", { name: "Apply source filter" }).click();

  await expect.poll(() => queryRequests.some((item) =>
    (item.filters || []).some((filter) =>
      filter.column.kind === "field" &&
      filter.column.name === "source" &&
      filter.value_mode === "all" &&
      filter.value_search === "dev"
    )
  )).toBeTruthy();

  await page.getByRole("button", { name: "Filter source" }).click();
  await page.getByRole("button", { name: "Invert source values" }).click();
  await page.getByRole("button", { name: "Apply source filter" }).click();

  await expect.poll(() => queryRequests.some((item) =>
    (item.filters || []).some((filter) =>
      filter.column.name === "source" &&
      filter.value_mode === "include" &&
      Array.isArray(filter.values) &&
      filter.values.length === 0
    )
  )).toBeTruthy();
});
```

- [ ] **Step 2: Run e2e and verify RED**

Run:

```powershell
npm run test:e2e -- tests/e2e/product-app.spec.js -g "Workspace header filter supports select all and invert semantics"
```

Expected: fail because the controls and payload fields do not exist yet.

- [ ] **Step 3: Implement TypeScript filter state**

In `frontend/src/domains/variants/types.ts`, add:

```ts
export type VariantGridValueMode = "all" | "include" | "exclude";
```

Add `value_mode?: VariantGridValueMode` and `value_search?: string | null` to `VariantGridColumnFilter`.

In `frontend/src/shared/ui/variantGridFilters.ts`, add the same fields to `VariantGridColumnFilterState`:

```ts
valueMode: VariantGridValueMode;
valueSearch: string;
```

`toApiFilters` should emit `value_mode` and `value_search` when a column has selected semantics. Existing decoded filters without those fields default to `include` and empty `valueSearch`.

- [ ] **Step 4: Implement Select All and Invert UI**

In `HeaderFilterPopover`:

- Add a `Select All` button using `optionSearch` as `valueSearch`.
- Add an `Invert` button.
- Use these transitions:
  - Select All -> `valueMode = "all"`, `values = []`, `valueSearch = optionSearch.trim()`
  - Invert from `all` -> `include []`
  - Invert from `include` -> `exclude` with the same values
  - Invert from `exclude` -> `include` with the same values
- Checkbox toggling from `all` converts to `exclude [value]`; toggling from `exclude` removes or adds excluded values; toggling from `include` keeps include behavior.

- [ ] **Step 5: Run focused e2e and verify GREEN**

Run the focused e2e command from Step 2. Expected: pass.

- [ ] **Step 6: Build product app**

Run:

```powershell
npm run build:app
```

Expected: Vite build succeeds and updates `app/static/product-app`.

---

### Task 3: Docs And Final Verification

**Files:**
- Modify: `docs/contracts.md`
- Modify: `app/static/product-app/*`

- [ ] **Step 1: Update API contract**

In `docs/contracts.md`, revise the filter routes section to state:

- `VariantGridColumnFilter` supports `value_mode: all | include | exclude`.
- `value_search` scopes the `all` candidate universe when using Select All after searching candidate values.
- filter options remain capped at 100 and sorted by name; count sorting is intentionally not part of this version.

- [ ] **Step 2: Run verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_variant_api.py tests/test_bulk_seed.py
npm run build:app
npm run test:e2e
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected:

- pytest passes.
- build passes.
- e2e passes.
- docs validation may still fail on existing archive/design historical links; changed active docs must not be implicated.

- [ ] **Step 3: Commit**

Commit all implementation, docs, tests, and rebuilt static assets:

```powershell
git add app frontend tests docs app/static/product-app design/2026-05-08-variant-grid-filter-select-all-invert-implementation-plan.md
git commit -m "feat: add variant grid select all filters"
```

