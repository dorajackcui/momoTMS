from pathlib import Path

from app.db import get_db_path, init_db
from app.services.branch.models import BranchRef
from app.services.read_models.derived.pivot_preview import PivotPreviewView
from app.services.branch.mutations import BranchMutationService
from app.services.project.service import ProjectService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.pivot import (
    PIVOT_STATUS_CHANGED,
    PIVOT_STATUS_INIT,
    PIVOT_STATUS_REVIEWED,
    pivot_changed_by_branch_ref,
)
from app.services.variant.state_coordinator import VariantStateCoordinator
from app.services.workflows.pivot_review import PivotReviewService


def reset_db() -> None:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    init_db()


def create_pivot_project() -> int:
    project = ProjectService().create_project(
        "Pivot Project",
        ["fr", "en", "de"],
        ["context"],
        "en",
        ["fr", "de"],
    )
    return int(project["project_id"])


def create_bound_variant(
    *,
    project_id: int,
    business_key: str,
    source: str,
    translations: dict[str, str],
    branch_refs: list[BranchRef],
) -> tuple[int, int]:
    entries = EntryService()
    catalog = VariantCatalogService()
    bindings = VariantStateCoordinator()
    entry = entries.get_or_create_entry(business_key, project_id=project_id)
    variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        catalog.build_content(
            f"{business_key}.xlsx",
            source,
            translations,
            {"context": business_key},
        ),
    )
    for branch_ref in branch_refs:
        bindings.bind(int(entry["entry_id"]), branch_ref, variant_id)
    return int(entry["entry_id"]), variant_id


def test_variant_create_initializes_pivot_status() -> None:
    reset_db()
    project_id = create_pivot_project()
    _entry_id, variant_id = create_bound_variant(
        project_id=project_id,
        business_key="pivot.init",
        source="Hello",
        translations={"en": "Hello", "fr": "Bonjour", "de": "Hallo"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )

    variant = VariantCatalogService().get_variant(variant_id)

    assert variant["pivot_status"] == PIVOT_STATUS_INIT
    assert pivot_changed_by_branch_ref(variant) is None
    assert variant["pivot_changed_at"] is None
    assert variant["pivot_reviewed_at"] is None
    assert variant["pivot_status_updated_at"] == variant["created_at"]


def test_direct_mutation_noop_and_non_pivot_update_leave_pivot_status_unchanged() -> None:
    reset_db()
    project_id = create_pivot_project()
    _entry_id, variant_id = create_bound_variant(
        project_id=project_id,
        business_key="pivot.noop",
        source="Hello",
        translations={"en": "Hello", "fr": "Bonjour", "de": "Hallo"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )
    service = BranchMutationService()

    noop = service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "pivot.noop",
                    "translations_by_lang": {"fr": "Bonjour"},
                }
            ],
        },
        project_id=project_id,
    )
    child_only = service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "pivot.noop",
                    "translations_by_lang": {"fr": "Bonjour v2"},
                }
            ],
        },
        project_id=project_id,
    )
    variant = VariantCatalogService().get_variant(variant_id)

    assert noop["report_rows"][0]["status"] == "NOOP"
    assert child_only["report_rows"][0]["status"] == "UPDATED_BOUND_VARIANT"
    assert variant["pivot_status"] == PIVOT_STATUS_INIT
    assert pivot_changed_by_branch_ref(variant) is None


def test_pivot_update_marks_changed_and_latest_owner_wins() -> None:
    reset_db()
    project_id = create_pivot_project()
    entry_id, variant_id = create_bound_variant(
        project_id=project_id,
        business_key="pivot.changed",
        source="Hello",
        translations={"en": "Hello", "fr": "Bonjour", "de": "Hallo"},
        branch_refs=[BranchRef.dev("2.4.3"), BranchRef.rel_current()],
    )
    catalog = VariantCatalogService()

    catalog.update_variant(
        variant_id,
        catalog.build_content(
            "pivot.changed.xlsx",
            "Hello",
            {"en": "Hello from dev", "fr": "Bonjour", "de": "Hallo"},
            {"context": "pivot.changed"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )
    after_dev = catalog.get_variant(variant_id)

    catalog.update_variant(
        variant_id,
        catalog.build_content(
            "pivot.changed.xlsx",
            "Hello",
            {"en": "Hello from rel", "fr": "Bonjour", "de": "Hallo"},
            {"context": "pivot.changed"},
        ),
        actor_scope=BranchRef.rel_current().as_tuple(),
    )
    after_rel = catalog.get_variant(variant_id)

    assert entry_id > 0
    assert after_dev["pivot_status"] == PIVOT_STATUS_CHANGED
    assert pivot_changed_by_branch_ref(after_dev) == "dev/2.4.3"
    assert after_dev["pivot_changed_at"] == after_dev["pivot_status_updated_at"]

    assert after_rel["pivot_status"] == PIVOT_STATUS_CHANGED
    assert pivot_changed_by_branch_ref(after_rel) == "rel/current"
    assert after_rel["pivot_changed_at"] == after_rel["pivot_status_updated_at"]


def test_manual_review_returns_expected_statuses_and_updates_variant() -> None:
    reset_db()
    project_id = create_pivot_project()
    catalog = VariantCatalogService()
    review_service = PivotReviewService()

    _entry_a, variant_a = create_bound_variant(
        project_id=project_id,
        business_key="pivot.reviewable",
        source="Hello",
        translations={"en": "Hello", "fr": "Bonjour", "de": "Hallo"},
        branch_refs=[BranchRef.dev("2.4.3"), BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_a,
        catalog.build_content(
            "pivot.reviewable.xlsx",
            "Hello",
            {"en": "Hello from dev", "fr": "Bonjour", "de": "Hallo"},
            {"context": "pivot.reviewable"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )

    _entry_b, variant_b = create_bound_variant(
        project_id=project_id,
        business_key="pivot.hidden",
        source="Hidden",
        translations={"en": "Hidden", "fr": "Cache", "de": "Versteckt"},
        branch_refs=[BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_b,
        catalog.build_content(
            "pivot.hidden.xlsx",
            "Hidden",
            {"en": "Hidden from rel", "fr": "Cache", "de": "Versteckt"},
            {"context": "pivot.hidden"},
        ),
        actor_scope=BranchRef.rel_current().as_tuple(),
    )

    _entry_c, variant_c = create_bound_variant(
        project_id=project_id,
        business_key="pivot.forbidden",
        source="Forbidden",
        translations={"en": "Forbidden", "fr": "Interdit", "de": "Verboten"},
        branch_refs=[BranchRef.dev("2.4.3"), BranchRef.rel_current()],
    )
    catalog.update_variant(
        variant_c,
        catalog.build_content(
            "pivot.forbidden.xlsx",
            "Forbidden",
            {"en": "Forbidden from rel", "fr": "Interdit", "de": "Verboten"},
            {"context": "pivot.forbidden"},
        ),
        actor_scope=BranchRef.rel_current().as_tuple(),
    )

    _entry_d, variant_d = create_bound_variant(
        project_id=project_id,
        business_key="pivot.init-only",
        source="Init",
        translations={"en": "Init", "fr": "Init", "de": "Init"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )

    reviewed = review_service.review(
        BranchRef.rel_current(),
        [variant_a],
        project_id=project_id,
    )
    dev_attempt = review_service.review(
        BranchRef.dev("2.4.3"),
        [variant_b, variant_c, variant_d, 999999],
        project_id=project_id,
    )

    reviewed_variant = catalog.get_variant(variant_a)

    assert reviewed["report_rows"] == [
        {
            "variant_id": variant_a,
            "business_key": "pivot.reviewable",
            "branch_ref": "rel/current",
            "status": "REVIEWED",
        }
    ]
    assert reviewed_variant["pivot_status"] == PIVOT_STATUS_REVIEWED
    assert pivot_changed_by_branch_ref(reviewed_variant) is None
    assert reviewed_variant["pivot_reviewed_at"] is not None

    statuses = {
        int(row["variant_id"]): row["status"]
        for row in dev_attempt["report_rows"]
    }
    assert statuses == {
        variant_b: "NOT_VISIBLE_IN_SCOPE",
        variant_c: "FORBIDDEN_BY_AUTHORITY",
        variant_d: "NOT_CHANGED",
        999999: "MISSING",
    }


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
