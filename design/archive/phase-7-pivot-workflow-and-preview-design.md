# Phase 7: Pivot Workflow And Preview

## Status

Design spec for completing the pivot preview contract and closing remaining gaps, based on a full audit of the current implementation.

## Goal

Complete the pivot layer without letting it become a separate top-level model. Specifically:

- confirm the current pivot design is correct and the preview flow works end-to-end
- confirm the pivot lifecycle is complete across all write paths
- confirm pivot does not conflict with other systems
- close the remaining functional gaps in the backend service layer
- defer frontend work to a later pass

## Audit Summary

The current implementation follows `archive/pivot-status-design.md` faithfully. The older `archive/pivot-language-design.md` (per-child drift / fingerprint approach) was correctly superseded and is not revisited.

### Design Correctness

The state machine, coordinator, and review service all match the design document:

- variant create → `init` (always, even if payload contains pivot language content)
- NOOP and non-pivot-language mutations do not change pivot state
- pivot-language mutation → `changed`, records actor branch as owner, latest writer wins
- manual review → `changed → reviewed`, clears owner, records `pivot_reviewed_at`
- review enforces 4 gates: exists, `pivot_status == changed`, visible in branch, actor authority >= owner authority
- 5 report statuses: `REVIEWED`, `NOT_CHANGED`, `NOT_VISIBLE_IN_SCOPE`, `FORBIDDEN_BY_AUTHORITY`, `MISSING`

No bugs found. Test coverage in `tests/test_variant_pivot.py` covers all state transitions and rejection paths.

### Lifecycle Completeness

Every write path that can affect a variant was checked for correct pivot interaction:

| Write Path | Triggers Pivot Refresh | Behavior | Correct |
|------------|----------------------|----------|--------|
| Direct mutation | Yes | `catalog.update_variant(actor_scope=...)` triggers pivot coordinator | Yes |
| Import batch mutation | Yes | Passes `actor_scope=target_branch.as_tuple()` | Yes |
| Authority-filtered content | No | Filtered content never enters merged payload, so normalized comparison sees no change | Yes |
| Bootstrap — new variant | No | `catalog.create_variant()` without actor_scope → `init` | Yes |
| Bootstrap — bind existing | No | Only creates binding, does not modify variant content | Yes |
| Replace | No | Pure binding rewrite, no pivot code | Yes |
| Trash (delete) | No | Removes binding, may trash variant; pivot fields preserved | Yes |
| Restore | No | Untrashes variant via lifecycle service, does not modify content | Yes |

Boundary case: a trashed variant with `pivot_status = changed` cannot be reviewed (no binding → `NOT_VISIBLE_IN_SCOPE`). This is correct — restore first, then review.

### System Conflict Matrix

| Interaction | Analysis | Conflict |
|------------|----------|----------|
| Pivot × Authority | Review reuses `AuthorityPolicy.key_for_branch()` directly | None |
| Pivot × Replace | Replace is binding rewrite; pivot is variant-local; `pivot_changed_by` preserves original actor after replace; review only checks authority level | None |
| Pivot × Bootstrap | Bootstrap only creates or binds; new variants get `init`; existing variants keep their pivot state | None |
| Pivot × Trash/Restore | Both preserve pivot fields; trashed+changed cannot be reviewed until restored | None |
| Pivot × Mutation Contract | Phase 4 semantic fields are orthogonal to pivot; pivot only checks normalized pivot-language value | None |
| Pivot × Read Models | PivotPreviewView uses standard read model pipeline via ProjectLiveVariantsDataset | None |

### Performance

Pivot is an optional feature, only enabled for multi-translation-language projects with a configured `pivot_language`. The `changed` row count is bounded by the number of variants whose pivot language has been modified since last review, expected to be well under 5,000.

| Path | Analysis | Conclusion |
|------|----------|------------|
| Pivot refresh (write) | Single-row: read old variant → compare one field → conditional UPDATE. O(1) | No issue |
| Pivot review (write) | Per-variant_id: 3 point lookups (variant, entry, binding) + 1 UPDATE. Batch of 100 = ~400 point queries | No issue |
| PivotPreviewView (read) | Uses `idx_variants_pivot_status` index; < 5k rows; branch_ref filter further reduces result set | No issue |
| Variant list endpoint (read) | Same index + pagination (default 50/page) | No issue |

### Current Implementation Inventory

Backend:

- `app/services/variant/pivot.py` — `VariantPivotCoordinator` with `refresh_variant()` and `review_variant()`
- `app/services/workflows/pivot_review.py` — `PivotReviewService.review()` with 4-gate validation
- `app/services/read_models/derived/pivot_preview.py` — `PivotPreviewView.build()` returns filtered variant list
- `app/routers/workflows.py` — `POST /api/projects/{project_id}/variants/pivot/review`
- `app/routers/inspection.py` — `GET /api/projects/{project_id}/variants` with `pivot_status` and `pivot_changed_by_branch_ref` filters

Frontend (exists, deferred from this phase):

- `frontend/src/pages/variants/VariantsPage.tsx` — Pivot Review Workspace with filters and batch review
- `frontend/src/domains/variants/api.ts` — `reviewPivot()` API call
- `frontend/src/pages/branches/BranchOpsSections.tsx` — pivot_status column in branch catalog

## Functional Gaps To Close

Three gaps remain in the backend service layer. None are bugs; all are missing capabilities that align pivot review with the preview contracts established in Phase 5.

### Gap 1: Pivot Review Effect Forecast (High Priority)

Replace, mutation, and bootstrap all follow a preview-then-execute pattern. Pivot review currently executes directly without a dry-run preview.

The operator cannot see upfront which variants will be reviewed, which will be blocked by authority, and which are not visible in the current branch.

Required:

- a `pivot_review_preview` method that accepts the same input as `review` (`branch_ref` + `variant_ids`) but only simulates the 4-gate checks without executing state transitions
- returns the same row-level report shape (`variant_id`, `business_key`, `status`) plus a summary
- the status vocabulary is identical to the execute path: `REVIEWABLE` (maps to would-be `REVIEWED`), `NOT_CHANGED`, `NOT_VISIBLE_IN_SCOPE`, `FORBIDDEN_BY_AUTHORITY`, `MISSING`
- exposed as `POST /api/projects/{project_id}/variants/pivot/review/preview`

This preview must be read-only: no pivot state changes, no side effects.

### Gap 2: PivotPreviewView Summary Counts (Medium Priority)

The current `PivotPreviewView.build()` returns raw rows but no aggregated summary. Other Phase 5 previews (replace, mutation, bootstrap) all include summary sections.

Required:

- add a `summary` key to the return value with at minimum:
  - `total_count`: total variants matching the filter
  - `by_branch`: grouped counts of changed variants per `pivot_changed_by_branch_ref`
- keep the existing row list in the response alongside the new summary

### Gap 3: Review-All-In-Branch Convenience Path (Medium Priority)

The current `review` method requires an explicit `variant_ids` list. The frontend works around this with a "Select all changed" button that first queries then submits.

Required:

- when `variant_ids` is empty or omitted, the review method should automatically discover all `changed` variants that are visible in the given `branch_ref` and that pass the authority gate
- this avoids a query-then-submit round trip and ensures the review set is consistent (no race between query and execute)
- the response shape is identical to the explicit-ids path

## Decisions

- pivot remains variant-local state; no branch-scoped pivot state is introduced
- the 3-state machine (`init`, `changed`, `reviewed`) is not extended; `reviewed` variants that receive a new pivot-language change transition back to `changed`
- `pivot_changed_by` records the historical actor branch, not the current binding owner; this is preserved across replace operations
- project-wide pivot queries (no branch_ref filter) continue to include all changed variants regardless of binding, including orphans
- frontend changes are deferred to a separate design pass after the backend service gaps are closed

## Non-Goals

- no per-child drift tracking or fingerprint (superseded design)
- no new pivot statuses
- no branch-level pivot state
- no automatic `changed → reviewed` transitions
- no frontend changes in this phase
- no changes to the existing review endpoint contract (only additions)

## Relationship To Phase Map

Phase 7 questions from `design/branch-infra-phase-map.md` and their answers:

1. **What pivot preview should display** — Two levels: (a) `PivotPreviewView` shows changed variants with summary counts; (b) pivot review effect_forecast shows per-variant dry-run results before executing review
2. **How pivot state changes relate to branch visibility** — pivot is variant-local; branch is only a filter for viewing and an actor for reviewing; trashed variants without bindings cannot be reviewed
3. **How pivot review authority relates to branch authority** — directly reuses `AuthorityPolicy.key_for_branch()`; no separate permission system
4. **What the operator-facing review flow should look like** — filter by branch + pivot_status=changed → preview effect_forecast → execute review; or use review-all for the branch

## Success Condition

After implementation:

- pivot review has a dry-run preview that returns the same report shape as execute
- PivotPreviewView returns summary counts alongside row data
- review-all-in-branch closes the query-then-submit gap
- no existing behavior is changed; all additions are backward compatible
- pivot preview and review speak one stable operator contract without reopening branch or lifecycle semantics
