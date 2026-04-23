# Phase 7: Pivot Workflow And Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three backend service gaps in the pivot workflow: (1) pivot review effect forecast preview, (2) PivotPreviewView summary counts, (3) review-all-in-branch convenience path.

**Architecture:** Each gap is a self-contained addition. Gap 1 adds a read-only preview method to `PivotReviewService` and a new router endpoint. Gap 2 enriches the existing `PivotPreviewView.build()` return value with a summary dict. Gap 3 extends the existing `PivotReviewService.review()` to auto-discover variants when `variant_ids` is empty.

**Tech Stack:** Python 3.12, FastAPI, SQLite, pytest

**Constraint:** No git operations. No frontend changes.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/services/workflows/pivot_review.py` | Modify | Add `preview()` method (Gap 1), extend `review()` for empty variant_ids (Gap 3) |
| `app/services/workflows/application.py` | Modify | Add `pivot_review_preview()` dispatch method |
| `app/services/read_models/derived/pivot_preview.py` | Modify | Add summary counts to `build()` return value (Gap 2) |
| `app/schemas.py` | Modify | Add `PivotReviewPreview` schema, make `PivotReviewRequest.variant_ids` optional |
| `app/routers/workflows.py` | Modify | Add `POST .../pivot/review/preview` endpoint |
| `tests/test_variant_pivot.py` | Modify | Add tests for all three gaps |

---

## Task 1: Pivot Review Effect Forecast Preview — Tests

**Files:**
- Modify: `tests/test_variant_pivot.py`

The preview method runs the same 4-gate checks as `review()` but does not execute state transitions. It returns an effect-forecast-shaped response. The status vocabulary mirrors the execute path: `REVIEWABLE` (would-be REVIEWED), `NOT_CHANGED`, `NOT_VISIBLE_IN_SCOPE`, `FORBIDDEN_BY_AUTHORITY`, `MISSING`.

- [ ] **Step 1: Write the preview test**

Add this test to the end of `tests/test_variant_pivot.py`:

```python
def test_pivot_review_preview_returns_forecast_without_state_change() -> None:
    reset_db()
    project_id = create_pivot_project()
    catalog = VariantCatalogService()
    review_service = PivotReviewService()

    _entry_a, variant_a = create_bound_variant(
        project_id=project_id,
        business_key="preview.reviewable",
        source="Hello",
        translations={"en": "Hello", "fr": "Bonjour", "de": "Hallo"},
        branch_refs=[BranchRef.dev("2.4.3"), BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_a,
        catalog.build_content(
            "preview.reviewable.xlsx",
            "Hello",
            {"en": "Hello from dev", "fr": "Bonjour", "de": "Hallo"},
            {"context": "preview.reviewable"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )

    _entry_b, variant_b = create_bound_variant(
        project_id=project_id,
        business_key="preview.hidden",
        source="Hidden",
        translations={"en": "Hidden", "fr": "Cache", "de": "Versteckt"},
        branch_refs=[BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_b,
        catalog.build_content(
            "preview.hidden.xlsx",
            "Hidden",
            {"en": "Hidden from rel", "fr": "Cache", "de": "Versteckt"},
            {"context": "preview.hidden"},
        ),
        actor_scope=BranchRef.rel_current().as_tuple(),
    )

    _entry_c, variant_c = create_bound_variant(
        project_id=project_id,
        business_key="preview.forbidden",
        source="Forbidden",
        translations={"en": "Forbidden", "fr": "Interdit", "de": "Verboten"},
        branch_refs=[BranchRef.dev("2.4.3"), BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_c,
        catalog.build_content(
            "preview.forbidden.xlsx",
            "Forbidden",
            {"en": "Forbidden from rel", "fr": "Interdit", "de": "Verboten"},
            {"context": "preview.forbidden"},
        ),
        actor_scope=BranchRef.rel_current().as_tuple(),
    )

    _entry_d, variant_d = create_bound_variant(
        project_id=project_id,
        business_key="preview.init-only",
        source="Init",
        translations={"en": "Init", "fr": "Init", "de": "Init"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )

    # Preview from dev/2.4.3 perspective
    result = review_service.preview(
        BranchRef.dev("2.4.3"),
        [variant_a, variant_b, variant_c, variant_d, 999999],
        project_id=project_id,
    )

    assert result["preview_kind"] == "effect_forecast"
    assert result["workflow_kind"] == "pivot_review"
    assert result["request_echo"] == {
        "branch_ref": "dev/2.4.3",
        "variant_ids": [variant_a, variant_b, variant_c, variant_d, 999999],
    }

    statuses = {
        int(row["variant_id"]): row["status"]
        for row in result["rows"]
    }
    assert statuses == {
        variant_a: "REVIEWABLE",
        variant_b: "NOT_VISIBLE_IN_SCOPE",
        variant_c: "FORBIDDEN_BY_AUTHORITY",
        variant_d: "NOT_CHANGED",
        999999: "MISSING",
    }

    assert result["summary"]["reviewable_count"] == 1
    assert result["summary"]["not_changed_count"] == 1
    assert result["summary"]["not_visible_in_branch_count"] == 1
    assert result["summary"]["forbidden_by_authority_count"] == 1
    assert result["summary"]["missing_count"] == 1
    assert result["summary"]["processed_count"] == 5

    # Verify no state change happened — variant_a should still be changed
    after = catalog.get_variant(variant_a)
    assert after["pivot_status"] == PIVOT_STATUS_CHANGED
    assert pivot_changed_by_branch_ref(after) == "dev/2.4.3"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_variant_pivot.py::test_pivot_review_preview_returns_forecast_without_state_change -v`

Expected: FAIL — `PivotReviewService` has no `preview` method.

---

## Task 2: Pivot Review Effect Forecast Preview — Implementation

**Files:**
- Modify: `app/services/workflows/pivot_review.py`

Add a `preview()` method that runs the same 4-gate logic as `review()` but never calls `self.pivot.review_variant()`. Uses `REVIEWABLE` instead of `REVIEWED` for would-be-reviewed rows.

- [ ] **Step 1: Add the preview method to PivotReviewService**

Add this method to the `PivotReviewService` class in `app/services/workflows/pivot_review.py`, after the `review()` method and before `_variant_visible_in_branch()`:

```python
    def preview(
        self,
        branch_ref: BranchRef,
        variant_ids: list[int],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)
        reviewable_count = 0
        not_changed_count = 0
        not_visible_count = 0
        forbidden_count = 0
        missing_count = 0
        rows: list[dict[str, object]] = []

        with get_conn() as conn:
            for variant_id in normalize_variant_ids(variant_ids):
                try:
                    variant = self.catalog.get_variant(variant_id, conn=conn)
                except KeyError:
                    missing_count += 1
                    rows.append({"variant_id": variant_id, "status": "MISSING"})
                    continue

                entry = self.entries.get_entry_by_id(int(variant["entry_id"]), conn=conn)
                if entry is None or int(entry["project_id"]) != project_id:
                    missing_count += 1
                    rows.append({"variant_id": variant_id, "status": "MISSING"})
                    continue

                if variant["pivot_status"] != PIVOT_STATUS_CHANGED:
                    not_changed_count += 1
                    rows.append(
                        {
                            "variant_id": variant_id,
                            "business_key": entry["business_key"],
                            "status": "NOT_CHANGED",
                        }
                    )
                    continue

                if not self._variant_visible_in_branch(int(entry["entry_id"]), variant_id, branch_ref, conn=conn):
                    not_visible_count += 1
                    rows.append(
                        {
                            "variant_id": variant_id,
                            "business_key": entry["business_key"],
                            "branch_ref": str(branch_ref),
                            "status": "NOT_VISIBLE_IN_SCOPE",
                        }
                    )
                    continue

                changed_owner_ref = pivot_changed_by_branch_ref(variant)
                if changed_owner_ref is None:
                    raise RuntimeError(f"changed pivot variant is missing owner metadata: {variant_id}")
                changed_owner = BranchRef.parse(changed_owner_ref)
                if AuthorityPolicy.key_for_branch(branch_ref) < AuthorityPolicy.key_for_branch(changed_owner):
                    forbidden_count += 1
                    rows.append(
                        {
                            "variant_id": variant_id,
                            "business_key": entry["business_key"],
                            "branch_ref": str(branch_ref),
                            "pivot_changed_by_branch_ref": changed_owner_ref,
                            "status": "FORBIDDEN_BY_AUTHORITY",
                        }
                    )
                    continue

                reviewable_count += 1
                rows.append(
                    {
                        "variant_id": variant_id,
                        "business_key": entry["business_key"],
                        "branch_ref": str(branch_ref),
                        "status": "REVIEWABLE",
                    }
                )

        summary = {
            "branch_ref": str(branch_ref),
            "processed_count": len(rows),
            "reviewable_count": reviewable_count,
            "not_changed_count": not_changed_count,
            "not_visible_in_branch_count": not_visible_count,
            "forbidden_by_authority_count": forbidden_count,
            "missing_count": missing_count,
        }
        return {
            "preview_kind": "effect_forecast",
            "workflow_kind": "pivot_review",
            "request_echo": {
                "branch_ref": str(branch_ref),
                "variant_ids": list(variant_ids),
            },
            "summary": summary,
            "rows": rows,
        }
```

Also add the missing `Any` import. The existing imports at the top of the file are:

```python
from __future__ import annotations

from app.db import get_conn
...
```

Add `from typing import Any` after the `__future__` import:

```python
from __future__ import annotations

from typing import Any

from app.db import get_conn
...
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `python -m pytest tests/test_variant_pivot.py::test_pivot_review_preview_returns_forecast_without_state_change -v`

Expected: PASS

- [ ] **Step 3: Run all existing pivot tests to check for regressions**

Run: `python -m pytest tests/test_variant_pivot.py -v`

Expected: All 5 tests PASS (4 existing + 1 new).

---

## Task 3: Preview Endpoint Wiring — Schema, Application Service, Router

**Files:**
- Modify: `app/schemas.py`
- Modify: `app/services/workflows/application.py`
- Modify: `app/routers/workflows.py`

- [ ] **Step 1: Add PivotReviewPreview schema to app/schemas.py**

Add the following after the `BranchReplacePreview` class (around line 147):

```python
class PivotReviewPreview(BaseModel):
    preview_kind: Literal["effect_forecast"]
    workflow_kind: Literal["pivot_review"]
    request_echo: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
```

Note: This does NOT extend `EffectForecastPreview` because that base class constrains `workflow_kind` to `Literal["branch_bootstrap", "branch_mutation", "branch_replace"]` which does not include `"pivot_review"`. A standalone schema with the same shape is the correct approach.

- [ ] **Step 2: Add pivot_review_preview to WorkflowApplicationService**

In `app/services/workflows/application.py`, add this method after the existing `pivot_review()` method:

```python
    def pivot_review_preview(
        self,
        branch_ref: str,
        variant_ids: list[int],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        parsed_branch_ref = BranchRef.parse(branch_ref)
        return self.pivot_review_service.preview(
            parsed_branch_ref,
            variant_ids,
            project_id=project_id,
        )
```

- [ ] **Step 3: Add the preview endpoint to the router**

In `app/routers/workflows.py`, add the following import to the existing import block from `app.schemas`:

```python
    PivotReviewPreview,
```

Then add the preview endpoint directly before the existing review endpoint (before line 150):

```python
@router.post("/api/projects/{project_id}/variants/pivot/review/preview", response_model=PivotReviewPreview)
def project_pivot_review_preview(project_id: int, payload: PivotReviewRequest) -> PivotReviewPreview:
    return handle_errors(
        lambda: PivotReviewPreview(
            **WorkflowApplicationService().pivot_review_preview(
                payload.branch_ref,
                payload.variant_ids,
                project_id=project_id,
            )
        )
    )
```

Important: the preview endpoint must come before the review endpoint in the router file so that FastAPI does not match `/review/preview` as `/review` with a path parameter.

- [ ] **Step 4: Run the full test suite to verify no regressions**

Run: `python -m pytest tests/test_variant_pivot.py tests/test_variant_api.py -v`

Expected: All tests PASS.

---

## Task 4: PivotPreviewView Summary Counts — Tests

**Files:**
- Modify: `tests/test_variant_pivot.py`

The `PivotPreviewView.build()` currently returns `{"rows": [...], "total_rows": int, "page": int, "page_size": int}`. After this change it should additionally include a `"summary"` key with `total_count` and `by_branch` grouped counts.

- [ ] **Step 1: Write the summary counts test**

Add this test to the end of `tests/test_variant_pivot.py`:

```python
from app.services.read_models.derived.pivot_preview import PivotPreviewView


def test_pivot_preview_view_includes_summary_counts() -> None:
    reset_db()
    project_id = create_pivot_project()
    catalog = VariantCatalogService()

    _entry_a, variant_a = create_bound_variant(
        project_id=project_id,
        business_key="summary.dev1",
        source="Hello",
        translations={"en": "Hello", "fr": "Bonjour", "de": "Hallo"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )
    catalog.update_variant(
        variant_a,
        catalog.build_content(
            "summary.dev1.xlsx",
            "Hello",
            {"en": "Hello changed", "fr": "Bonjour", "de": "Hallo"},
            {"context": "summary.dev1"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )

    _entry_b, variant_b = create_bound_variant(
        project_id=project_id,
        business_key="summary.dev2",
        source="World",
        translations={"en": "World", "fr": "Monde", "de": "Welt"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )
    catalog.update_variant(
        variant_b,
        catalog.build_content(
            "summary.dev2.xlsx",
            "World",
            {"en": "World changed", "fr": "Monde", "de": "Welt"},
            {"context": "summary.dev2"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )

    _entry_c, variant_c = create_bound_variant(
        project_id=project_id,
        business_key="summary.rel",
        source="Bye",
        translations={"en": "Bye", "fr": "Au revoir", "de": "Tschuss"},
        branch_refs=[BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_c,
        catalog.build_content(
            "summary.rel.xlsx",
            "Bye",
            {"en": "Bye changed", "fr": "Au revoir", "de": "Tschuss"},
            {"context": "summary.rel"},
        ),
        actor_scope=BranchRef.rel_current().as_tuple(),
    )

    result = PivotPreviewView().build(project_id=project_id)

    assert "summary" in result
    assert result["summary"]["total_count"] == 3
    assert result["summary"]["by_branch"] == {
        "dev/2.4.3": 2,
        "rel/current": 1,
    }

    # Branch-filtered query
    dev_result = PivotPreviewView().build(
        project_id=project_id,
        branch_ref=BranchRef.dev("2.4.3"),
    )
    assert dev_result["summary"]["total_count"] == 2
    assert dev_result["summary"]["by_branch"] == {"dev/2.4.3": 2}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_variant_pivot.py::test_pivot_preview_view_includes_summary_counts -v`

Expected: FAIL — `"summary"` key not present in result.

---

## Task 5: PivotPreviewView Summary Counts — Implementation

**Files:**
- Modify: `app/services/read_models/derived/pivot_preview.py`

Enrich the `build()` return value with a `summary` key. The summary is computed from the returned rows by counting `pivot_changed_by_branch_ref` values.

- [ ] **Step 1: Update PivotPreviewView.build() to include summary**

Replace the entire content of `app/services/read_models/derived/pivot_preview.py` with:

```python
from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.branch.models import BranchRef
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.read_models.datasets.live_variants import ProjectLiveVariantsDataset
from app.services.read_models.selectors import VariantFilter
from app.services.variant.records import PivotStatus


class PivotPreviewView:
    def __init__(self, *, live_variants: ProjectLiveVariantsDataset | None = None) -> None:
        self.live_variants = live_variants or ProjectLiveVariantsDataset()

    def build(
        self,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
        branch_ref: BranchRef | None = None,
        pivot_status: PivotStatus | None = "changed",
    ) -> dict[str, Any]:
        filters = VariantFilter(
            state="all",
            branch_refs=(branch_ref,) if branch_ref is not None else (),
            pivot_status=pivot_status,
        )
        result = self.live_variants.list(filters, project_id=project_id)
        rows = result.get("rows", [])
        by_branch: dict[str, int] = dict(
            Counter(
                row["pivot_changed_by_branch_ref"]
                for row in rows
                if row.get("pivot_changed_by_branch_ref")
            )
        )
        result["summary"] = {
            "total_count": len(rows),
            "by_branch": by_branch,
        }
        return result
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `python -m pytest tests/test_variant_pivot.py::test_pivot_preview_view_includes_summary_counts -v`

Expected: PASS

- [ ] **Step 3: Run all pivot tests to check for regressions**

Run: `python -m pytest tests/test_variant_pivot.py -v`

Expected: All tests PASS.

---

## Task 6: Review-All-In-Branch — Tests

**Files:**
- Modify: `tests/test_variant_pivot.py`

When `variant_ids` is empty (or omitted), `review()` should auto-discover all `changed` variants visible in the given branch that pass the authority gate, and review them.

- [ ] **Step 1: Write the review-all test**

Add this test to the end of `tests/test_variant_pivot.py`:

```python
def test_review_all_in_branch_discovers_and_reviews_eligible_variants() -> None:
    reset_db()
    project_id = create_pivot_project()
    catalog = VariantCatalogService()
    review_service = PivotReviewService()

    _entry_a, variant_a = create_bound_variant(
        project_id=project_id,
        business_key="all.reviewable1",
        source="Hello",
        translations={"en": "Hello", "fr": "Bonjour", "de": "Hallo"},
        branch_refs=[BranchRef.dev("2.4.3"), BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_a,
        catalog.build_content(
            "all.reviewable1.xlsx",
            "Hello",
            {"en": "Hello changed", "fr": "Bonjour", "de": "Hallo"},
            {"context": "all.reviewable1"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )

    _entry_b, variant_b = create_bound_variant(
        project_id=project_id,
        business_key="all.reviewable2",
        source="World",
        translations={"en": "World", "fr": "Monde", "de": "Welt"},
        branch_refs=[BranchRef.dev("2.4.3"), BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_b,
        catalog.build_content(
            "all.reviewable2.xlsx",
            "World",
            {"en": "World changed", "fr": "Monde", "de": "Welt"},
            {"context": "all.reviewable2"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )

    # variant_c: changed by rel/current — dev cannot review (authority)
    _entry_c, variant_c = create_bound_variant(
        project_id=project_id,
        business_key="all.forbidden",
        source="Forbidden",
        translations={"en": "Forbidden", "fr": "Interdit", "de": "Verboten"},
        branch_refs=[BranchRef.dev("2.4.3"), BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_c,
        catalog.build_content(
            "all.forbidden.xlsx",
            "Forbidden",
            {"en": "Forbidden changed", "fr": "Interdit", "de": "Verboten"},
            {"context": "all.forbidden"},
        ),
        actor_scope=BranchRef.rel_current().as_tuple(),
    )

    # variant_d: not changed (init) — should not appear
    _entry_d, _variant_d = create_bound_variant(
        project_id=project_id,
        business_key="all.init",
        source="Init",
        translations={"en": "Init", "fr": "Init", "de": "Init"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )

    # Review all from rel/current — should review a, b, c (all visible, rel has authority)
    rel_result = review_service.review(
        BranchRef.rel_current(),
        [],
        project_id=project_id,
    )
    rel_statuses = {
        int(row["variant_id"]): row["status"]
        for row in rel_result["report_rows"]
    }
    assert rel_statuses == {
        variant_a: "REVIEWED",
        variant_b: "REVIEWED",
        variant_c: "REVIEWED",
    }
    assert rel_result["summary"]["reviewed_count"] == 3

    # Reset: make variant_a changed again for the dev review test
    catalog.update_variant(
        variant_a,
        catalog.build_content(
            "all.reviewable1.xlsx",
            "Hello",
            {"en": "Hello changed again", "fr": "Bonjour", "de": "Hallo"},
            {"context": "all.reviewable1"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )

    # Review all from dev/2.4.3 — variant_a is reviewable (changed by dev)
    dev_result = review_service.review(
        BranchRef.dev("2.4.3"),
        [],
        project_id=project_id,
    )
    dev_statuses = {
        int(row["variant_id"]): row["status"]
        for row in dev_result["report_rows"]
    }
    assert dev_statuses == {variant_a: "REVIEWED"}
    assert dev_result["summary"]["reviewed_count"] == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_variant_pivot.py::test_review_all_in_branch_discovers_and_reviews_eligible_variants -v`

Expected: FAIL — empty `variant_ids` produces an empty result (the current `normalize_variant_ids([])` returns `[]`, so the loop body never executes).

---

## Task 7: Review-All-In-Branch — Implementation

**Files:**
- Modify: `app/services/workflows/pivot_review.py`
- Modify: `app/services/read_models/derived/pivot_preview.py` (read-only dependency, no change needed)

When `variant_ids` is empty, discover all `changed` variants visible in the branch via `PivotPreviewView`, then filter by authority and review the eligible ones.

- [ ] **Step 1: Add discovery logic to the review method**

In `app/services/workflows/pivot_review.py`, add the `PivotPreviewView` import at the top:

```python
from app.services.read_models.derived.pivot_preview import PivotPreviewView
```

Then modify the `review()` method. Replace the first two lines after the docstring:

```python
    def review(
        self,
        branch_ref: BranchRef,
        variant_ids: list[int],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, list[dict[str, object]] | dict[str, int] | str]:
        self.projects.require_project(project_id)

        if not variant_ids:
            variant_ids = self._discover_reviewable_variant_ids(
                branch_ref, project_id=project_id
            )

        reviewed_count = 0
```

Then add the discovery helper method before `_variant_visible_in_branch`:

```python
    def _discover_reviewable_variant_ids(
        self,
        branch_ref: BranchRef,
        *,
        project_id: int,
    ) -> list[int]:
        preview_result = PivotPreviewView().build(
            project_id=project_id,
            branch_ref=branch_ref,
            pivot_status="changed",
        )
        candidate_ids = []
        for row in preview_result.get("rows", []):
            changed_ref = row.get("pivot_changed_by_branch_ref")
            if changed_ref is None:
                continue
            changed_owner = BranchRef.parse(changed_ref)
            if AuthorityPolicy.key_for_branch(branch_ref) >= AuthorityPolicy.key_for_branch(changed_owner):
                candidate_ids.append(int(row["variant_id"]))
        return candidate_ids
```

This pre-filters by authority so the main loop only processes variants that will succeed, keeping the review-all path efficient and consistent (no race between discovery and execution since both happen in the same request).

- [ ] **Step 2: Run the test to verify it passes**

Run: `python -m pytest tests/test_variant_pivot.py::test_review_all_in_branch_discovers_and_reviews_eligible_variants -v`

Expected: PASS

- [ ] **Step 3: Run all pivot tests to check for regressions**

Run: `python -m pytest tests/test_variant_pivot.py -v`

Expected: All tests PASS (4 original + 3 new = 7 total).

---

## Task 8: Schema Update For Optional variant_ids

**Files:**
- Modify: `app/schemas.py`

The review endpoint should accept an empty `variant_ids` list or omit it entirely to trigger review-all-in-branch.

- [ ] **Step 1: Make variant_ids optional in PivotReviewRequest**

In `app/schemas.py`, change the `PivotReviewRequest` class:

From:
```python
class PivotReviewRequest(BaseModel):
    branch_ref: str
    variant_ids: list[int]
```

To:
```python
class PivotReviewRequest(BaseModel):
    branch_ref: str
    variant_ids: list[int] = Field(default_factory=list)
```

This preserves backward compatibility — existing callers that send `variant_ids` continue to work; omitting it defaults to empty list which triggers review-all.

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest tests/test_variant_pivot.py tests/test_variant_api.py -v`

Expected: All tests PASS.

---

## Task 9: Preview Endpoint Also Supports Review-All Discovery

**Files:**
- Modify: `tests/test_variant_pivot.py`

The preview method should also support empty `variant_ids` for discovery preview.

- [ ] **Step 1: Write the preview-all test**

Add this test to the end of `tests/test_variant_pivot.py`:

```python
def test_pivot_review_preview_with_empty_variant_ids_discovers_all() -> None:
    reset_db()
    project_id = create_pivot_project()
    catalog = VariantCatalogService()
    review_service = PivotReviewService()

    _entry_a, variant_a = create_bound_variant(
        project_id=project_id,
        business_key="previewall.a",
        source="Hello",
        translations={"en": "Hello", "fr": "Bonjour", "de": "Hallo"},
        branch_refs=[BranchRef.dev("2.4.3"), BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_a,
        catalog.build_content(
            "previewall.a.xlsx",
            "Hello",
            {"en": "Hello changed", "fr": "Bonjour", "de": "Hallo"},
            {"context": "previewall.a"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )

    _entry_b, variant_b = create_bound_variant(
        project_id=project_id,
        business_key="previewall.b",
        source="World",
        translations={"en": "World", "fr": "Monde", "de": "Welt"},
        branch_refs=[BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_b,
        catalog.build_content(
            "previewall.b.xlsx",
            "World",
            {"en": "World changed", "fr": "Monde", "de": "Welt"},
            {"context": "previewall.b"},
        ),
        actor_scope=BranchRef.rel_current().as_tuple(),
    )

    # Preview-all from rel/current — should discover both
    result = review_service.preview(
        BranchRef.rel_current(),
        [],
        project_id=project_id,
    )

    statuses = {
        int(row["variant_id"]): row["status"]
        for row in result["rows"]
    }
    assert statuses == {
        variant_a: "REVIEWABLE",
        variant_b: "REVIEWABLE",
    }
    assert result["summary"]["reviewable_count"] == 2
    assert result["summary"]["processed_count"] == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_variant_pivot.py::test_pivot_review_preview_with_empty_variant_ids_discovers_all -v`

Expected: FAIL — `preview()` with empty `variant_ids` returns empty rows.

---

## Task 10: Preview Also Supports Review-All Discovery — Implementation

**Files:**
- Modify: `app/services/workflows/pivot_review.py`

- [ ] **Step 1: Add discovery to the preview method**

In the `preview()` method of `PivotReviewService`, add the same discovery branch after `self.projects.require_project(project_id)`:

```python
    def preview(
        self,
        branch_ref: BranchRef,
        variant_ids: list[int],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.projects.require_project(project_id)

        if not variant_ids:
            variant_ids = self._discover_all_changed_variant_ids(
                branch_ref, project_id=project_id
            )

        reviewable_count = 0
```

Note that `preview()` uses a different discovery method than `review()`. The preview shows ALL changed variants in the branch (including authority-blocked ones) so the operator can see the full picture. Add this second discovery helper:

```python
    def _discover_all_changed_variant_ids(
        self,
        branch_ref: BranchRef,
        *,
        project_id: int,
    ) -> list[int]:
        preview_result = PivotPreviewView().build(
            project_id=project_id,
            branch_ref=branch_ref,
            pivot_status="changed",
        )
        return [int(row["variant_id"]) for row in preview_result.get("rows", [])]
```

The difference:
- `_discover_reviewable_variant_ids` (used by `review()`) pre-filters by authority — only processes variants that will succeed, avoiding unnecessary gate checks.
- `_discover_all_changed_variant_ids` (used by `preview()`) returns ALL changed variants visible in the branch — the preview loop then classifies each one (REVIEWABLE, FORBIDDEN_BY_AUTHORITY, etc.) so the operator sees the complete picture.

- [ ] **Step 2: Run the test to verify it passes**

Run: `python -m pytest tests/test_variant_pivot.py::test_pivot_review_preview_with_empty_variant_ids_discovers_all -v`

Expected: PASS

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/test_variant_pivot.py -v`

Expected: All 8 tests PASS.

---

## Task 11: Final Verification

**Files:** None (read-only verification)

- [ ] **Step 1: Run the full project test suite**

Run: `python -m pytest tests/ -v`

Expected: All tests PASS.

- [ ] **Step 2: Verify the design doc success conditions are met**

Check each success condition from `design/phase-7-pivot-workflow-and-preview-design.md`:

1. Pivot review has a dry-run preview that returns the same report shape as execute → `PivotReviewService.preview()` returns effect_forecast with REVIEWABLE/NOT_CHANGED/NOT_VISIBLE_IN_SCOPE/FORBIDDEN_BY_AUTHORITY/MISSING statuses
2. PivotPreviewView returns summary counts alongside row data → `build()` now returns `{"summary": {"total_count": int, "by_branch": {...}}, "rows": [...], ...}`
3. Review-all-in-branch closes the query-then-submit gap → empty `variant_ids` triggers auto-discovery in both `review()` and `preview()`
4. No existing behavior is changed; all additions are backward compatible → existing tests still pass; `variant_ids` defaults to `[]` via `Field(default_factory=list)`
