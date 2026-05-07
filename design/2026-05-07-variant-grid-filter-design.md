# Variant Grid Header Filter Design

Date: 2026-05-07

## Purpose

Add WPS/Excel-like column filtering to the product variant grids while keeping large
projects usable. The target project size for all-branch workspace browsing is
300k-500k live variants, so filtering must be backed by server-side queries instead
of local page filtering.

This note is a change design, not current runtime documentation. When implemented,
the stable API and product behavior should be copied into the matching owner doc
under `docs/`.

## Current State

- `VariantGrid` currently exposes inline header text inputs only for
  `business_key` and `source`.
- Existing rows APIs are GET routes:
  - `GET /api/projects/{project_id}/variants`
  - `GET /api/projects/{project_id}/branches/{branch_ref:path}/rows`
  - `GET /api/projects/{project_id}/scopes/{scope_ref:path}/rows`
- Current API filtering is limited to `search_business_key`, `search_source`,
  project live state, branch refs, and pivot owner/status in the project-wide
  variants route.
- Rows are paged at 100 in the current frontend, but operator preview value is
  not improved by 100 rows compared with 50 rows.

## Goals

- Every visible grid field has a header filter affordance:
  `business_key`, `file_name`, `source`, translations, remarks, `branch`,
  `state`, and `pivot_status`.
- Each column supports both text search and exact-value selection.
- Text search filters the whole current data scope, not only the current page.
- Exact-value filter lists show only the first 100 distinct candidate values.
- Table row previews and pages use 50 rows.
- Workspace scope follows the current workspace context:
  - no selected branch means all project live variants, excluding trashed rows
  - selected branch means that branch only
  - project state filtering applies only to all-project workspace queries
- Release and Dev browse pages filter only their current branch.
- Existing GET rows APIs remain compatible.

## Non-Goals

- Do not add schema editing or any legacy compatibility route.
- Do not introduce full-text search in the first implementation.
- Do not make hidden columns filterable from the grid header.
- Do not add date range filtering for timestamp fields in this pass.
- Do not rely on browser-side filtering for correctness.

## Chosen Approach

Add dedicated POST APIs for the richer grid contract:

- `POST /api/projects/{project_id}/variants/query`
- `POST /api/projects/{project_id}/variants/filter-options`

The existing GET APIs continue to support current simple reads and compatibility.
The POST body can represent dynamic translation and remark filters without awkward
query parameter naming, and it leaves room for a future search-index-backed
implementation without changing the frontend contract.

## Query Contract

### Column References

Column references use a typed shape:

```json
{ "kind": "field", "name": "source" }
```

Supported references:

- `field:business_key`
- `field:file_name`
- `field:source`
- `field:branch`
- `field:state`
- `field:pivot_status`
- `translation:<schema translation column>`
- `remark:<schema remark column>`

Backends must validate translation and remark names against the project schema.

### Row Query

Request:

```json
{
  "scope": { "kind": "project" },
  "state": "all",
  "filters": [
    {
      "column": { "kind": "field", "name": "source" },
      "text": "rose",
      "values": []
    },
    {
      "column": { "kind": "translation", "name": "zh-Hans" },
      "text": "",
      "values": ["Red rose"]
    }
  ],
  "page": 1,
  "page_size": 50
}
```

Branch scope:

```json
{
  "scope": { "kind": "branch", "branch_ref": "rel/current" },
  "filters": [],
  "page": 1,
  "page_size": 50
}
```

Response:

```json
{
  "rows": [],
  "page": 1,
  "page_size": 50,
  "has_next_page": false,
  "total_rows": 0,
  "total_rows_exact": true
}
```

The row shape should reuse `ProjectVariantRow`.

`page_size` defaults to 50 and should be capped at 50 for this grid query.
The initial implementation may keep exact counts, but the contract includes
`has_next_page` and `total_rows_exact` so later implementations can avoid expensive
exact counts for very broad contains queries.

### Filter Options Query

Request:

```json
{
  "scope": { "kind": "project" },
  "state": "all",
  "target_column": { "kind": "field", "name": "source" },
  "filters": [],
  "option_search": "rose",
  "limit": 100
}
```

Response:

```json
{
  "values": [
    { "value": "Rose", "label": "Rose", "count": null }
  ],
  "limit": 100,
  "has_more": false
}
```

`limit` defaults to 100 and must be capped at 100. Option values should be
distinct values from the target column. Blank values are represented as JSON
`null` and displayed in the UI as `(blank)`.

The options query applies all filters except filters targeting `target_column`.
This creates spreadsheet-style dependent filter lists.

## Filter Semantics

- `text` means case-insensitive contains.
- `values` means exact match against one of the listed values.
- For one column, `text` and `values` are combined with AND.
- Across columns, filters are combined with AND.
- Empty text and empty values are ignored.
- Null exact values match blank or missing values.
- `branch` exact values match rows currently bound to that branch.
- `state` exact values match resolved live state: `active` or `orphan`.
- `pivot_status` exact values match `init`, `changed`, or `reviewed`.

## Backend Query Design

The query service should live with the read-model layer rather than variant-domain
write services.

Suggested structure:

- a new read-model grid filter module for request-domain parsing, column
  validation, and SQL predicate generation
- `ReadModelRepository`
  - row selection for rich grid filters
  - distinct option selection for rich grid filters
- `ProjectLiveVariantsDataset`
  - project-wide row query facade
  - options query facade
- `ScopeMembershipDataset`
  - branch-scope row query facade
  - branch-scope options query facade

The SQL path should:

1. Build a base row set from `variants v JOIN entries e`.
2. Always require `e.project_id = ?` and `v.trashed_at IS NULL`.
3. Apply project state:
   - `active`: binding exists
   - `orphan`: binding does not exist
   - `all`: active plus orphan
4. Apply branch scope with `EXISTS scope_bindings`.
5. Apply field, translation, remark, branch, state, and pivot predicates.
6. Page row ids first, then hydrate rows through the existing read-model hydrator.

The options path should reuse the same base filters, remove the target column's
own filters, and select distinct target values with a server-side limit of 100.

## Performance Design

The first implementation is SQL-backed and should be careful about broad scans.

Required guardrails:

- Row queries run only after explicit Apply or Enter in the UI.
- Header option search may be debounced, but it only asks for distinct values and
  is limited to 100 results.
- Row pages use 50 rows.
- Hydration happens only for the selected page, never for the full matched set.
- The API exposes `has_next_page` so exact counts can be relaxed later.

Schema/index work:

- Add `variant_translations(lang, variant_id)`.
- Add `variant_remarks(remark_key, variant_id)`.
- Consider `variant_translations(lang, target_text, variant_id)` if exact value
  filtering on translations is common.
- Consider `variant_remarks(remark_key, remark_value, variant_id)` if exact value
  filtering on remarks is common.

Known limitation:

- `LIKE '%term%'` contains queries cannot make strong use of normal B-tree
  indexes. The SQL implementation is expected to be acceptable for explicit,
  user-triggered queries, especially after scope/state filters narrow the row set.
  If operators require near-real-time contains search across all source and
  translation text at 300k-500k variants, add a search-index implementation behind
  the same POST contract.

## Frontend UX

Replace inline header inputs with a header filter button on every visible
filterable column.

The filter popover contains:

- Search input for the column contains filter.
- Distinct value checklist loaded from `filter-options`.
- `Apply` button.
- `Clear column` button.
- A small message when only the first 100 values are shown.

Behavior:

- Typing in the column search input does not refresh rows until Apply or Enter.
- Changing checklist values does not refresh rows until Apply.
- A filtered column has an active visual state in the header.
- A toolbar action clears all filters.
- Long option labels are truncated visually but expose the full value with native
  title text.
- `(blank)` represents null, empty, or missing values.
- Hidden translation, remark, or pivot groups do not show header filters until
  the group is visible.
- Workspace keeps filter state in the URL. Release and Dev may start with local
  state, but URL state is preferred if the implementation can keep it readable.

## Testing Strategy

Backend tests:

- Rich query filters each supported field type.
- Translation and remark text filters search the whole selected scope.
- Exact value filters match selected values and null blanks.
- Multiple column filters combine with AND.
- Filter options ignore the target column's own filters but apply other filters.
- Project scope respects `active`, `orphan`, `all`, and optional branch refs.
- Branch scope returns only that branch.
- Page size defaults to 50 and is capped at 50.
- Option limit defaults to 100 and is capped at 100.

Frontend/e2e tests:

- Workspace source search updates the POST query and returns filtered rows.
- Workspace branch selection constrains rich query scope.
- Release and Dev browse pages query branch scope.
- Header filter active state appears after Apply and clears correctly.
- Distinct options render with a first-100 notice when `has_more` is true.

Verification:

- Run focused API tests after backend work.
- Run `npm run build:app` after frontend work.
- Run Playwright e2e for visible grid workflows.
- Run docs validation if runtime docs or route inventories are updated during
  implementation.

## Open Follow-Ups

- Decide during implementation whether Release and Dev filter state should also
  be encoded in the URL.
- Decide whether exact-value composite indexes with text values are needed in
  the first implementation or after measuring real project data.
- Consider a later FTS or search shadow table if contains queries over 300k-500k
  variants are too slow.
