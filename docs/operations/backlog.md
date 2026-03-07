# Development Backlog

This file is the working checklist for the next phase of Momo TMS.

Rules:

- Convert completed items from `[ ]` to `[x]`.
- If one item grows too large, split it into smaller checklist items before implementation.
- Prefer closing P0 items before starting new P1 or P2 work.
- If code behavior changes, update the matching docs in the same change.

## P0: Stabilize the Variant-Native Runtime

- [x] Move project bootstrap away from compatibility-shaped state where practical, and define which parts of `GET /api/state` remain compatibility-only.
- [x] Remove new business logic from [`app/services/variant/compatibility.py`](/Users/zhiyangcui/Documents/Momo_TMS/app/services/variant/compatibility.py); keep it as adapter code only.
- [x] Reduce router and workflow dependence on [`app/services/variant/facade.py`](/Users/zhiyangcui/Documents/Momo_TMS/app/services/variant/facade.py) when split services already exist.
- [x] Make trash/delete semantics explicitly variant-and-scope aware instead of entry-wide compatibility behavior.
- [x] Decide whether release hotfix APIs stay legacy-shaped or gain project-scoped routes, then implement the chosen shape consistently.
- [x] Audit all default-project compatibility routes and mark each one as either:
  keep temporarily / replace with project-scoped route / delete after frontend-workbench migration

## P0: Strengthen Runtime Safety

- [x] Isolate tests from the shared `data/tms.db` file so backend tests and E2E can run without stepping on each other.
- [x] Add router tests for project ownership boundaries on imports, jobs, reports, and artifacts.
- [x] Add negative-path API tests for invalid payloads on promote, fill, QA, upload preview, and project creation.
- [x] Add coverage for compatibility routes that should still work for project `1`.
- [x] Add regression tests for lifecycle edges:
  retained variant reuse / orphan refresh after rebind / restore after trash / promote cleanup across a version line

## P0 Audit Snapshot

Keep temporarily:

- [x] `/api/state`
- [x] `/api/demo/reset`
- [x] `/api/strings`
- [x] `/api/strings/{business_key}`
- [x] `/api/imports/directory`
- [x] `/api/imports/upload-folder`
- [x] `/api/imports/upload-folder/preview`
- [x] `/api/imports`
- [x] `/api/imports/{import_batch_id}/report`
- [x] `/api/jobs`
- [x] `/api/jobs/{job_id}`
- [x] `/api/jobs/{job_id}/report`
- [x] `/api/jobs/{job_id}/artifact/{name}`
- [x] `/api/dev-versions`
- [x] `/api/dev-versions/{version}`
- [x] `/api/dev-versions/import`
- [x] `/api/scopes/summary`
- [x] `/api/scopes/compare`
- [x] `/api/translation-queue`
- [x] `/api/master/entries/{business_key}`
- [x] `/api/master/search`
- [x] `/api/promote/preview`
- [x] `/api/promote/execute`
- [x] `/api/fill`
- [x] `/api/fill/upload-folder`
- [x] `/api/qa`
- [x] `/api/qa/upload-folder`

Replace now:

- [x] `/api/rel/hotfix/active`
- [x] `/api/rel/hotfix/passive`
- [x] `/api/trash/delete`
- [x] `/api/trash/restore`

Delete after compatibility-page migration:

- [x] All "keep temporarily" compatibility routes stay frozen in P0 and move to P1/P2 reassessment instead of immediate deletion.

## P1: Finish Product/API Convergence

- [x] Make `/app` the primary product surface and document which tasks still require `/variant-workbench`.
- [x] Review the `/app` flows against current APIs and remove remaining dependence on compatibility-only routes.
- [x] Remove `/workbench` as a runtime surface and return `410 Gone`.
- [x] Freeze `/variant-workbench` as a deprecated internal regression page instead of a product path.
- [x] Add a small product bootstrap contract doc for `GET /api/projects/{project_id}/state`.

## P1: Tighten Domain and API Boundaries

- [x] Add dedicated read-only entry-variant and retained-variant inspection endpoints.
- [x] Make schema immutability explicit in product UI and API docs.
- [x] Normalize error handling so invalid scope refs, missing project ownership, and missing artifacts return deliberate 4xx responses.
- [x] Use explicit product-facing and compatibility-facing state model names in [`app/schemas.py`](/Users/zhiyangcui/Documents/Momo_TMS/app/schemas.py).

## P1: Performance Work That Matters Soon

- [x] Reduce in-memory scope hydration in [`app/services/read_models/service.py`](/Users/zhiyangcui/Documents/Momo_TMS/app/services/read_models/service.py) for compare and queue.
- [x] Push compare filtering, search selection, and master search closer to repository-level selection.
- [x] Measure import, dev import, fill, and QA against larger sample bundles and record timing baselines.
- [x] Add job-stage summaries for long-running flows so operators can see whether time is spent in parsing, binding, fill, QA, or artifact generation.

## P2: Product and Operator Improvements

- [x] Improve job/report inspection in `/app/imports` so operators can move between import, dev import, fill, QA, and promote runs more easily.
- [x] Add explicit retained/orphan inspection tools for project-scoped debugging.
- [x] Improve project switching and project-empty-state behavior in `/app`.
- [x] Keep release hotfix as an internal validation-only action instead of adding a product UI.

## P2: Documentation and Engineering Hygiene

- [x] Keep [`docs/runtime/api-surface.md`](/Users/zhiyangcui/Documents/Momo_TMS/docs/runtime/api-surface.md) aligned with router changes.
- [x] Keep [`docs/runtime/frontend.md`](/Users/zhiyangcui/Documents/Momo_TMS/docs/runtime/frontend.md) aligned with actual `/app` behavior.
- [x] Add a short ADR-style note when compatibility routes are intentionally removed or frozen.
- [x] When a domain boundary becomes stable, record the source-of-truth module in docs so future refactors do not reintroduce ambiguity.

## Suggested Execution Order

1. Test DB isolation and API negative-path coverage.
2. Compatibility-route audit and variant-native cleanup.
3. Trash/hotfix/bootstrap boundary cleanup.
4. `/app` and workbench responsibility decisions.
5. Read-model performance work.
