from pathlib import Path

from app.db import get_db_path, init_db
from app.services.project.service import ProjectService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.pivot import (
    MISSING_CHILD,
    MISSING_PARENT,
    PIVOT_IN_SYNC,
    PIVOT_OUT_OF_SYNC,
    VariantPivotRepository,
    derive_pivot_sync_status,
)


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
        {"fr": "en", "de": "en"},
    )
    return int(project["project_id"])


def pivot_status_by_lang(project_id: int, variant_id: int) -> dict[str, str]:
    schema = ProjectService().get_schema(project_id)
    variant = VariantCatalogService().get_variant(variant_id)
    sync_states = VariantPivotRepository().list_sync_states([variant_id])
    results: dict[str, str] = {}
    for child_lang, pivot_lang in schema["translation_pivots"].items():
        if pivot_lang is None:
            continue
        sync_state = sync_states[(variant_id, child_lang)]
        results[child_lang] = derive_pivot_sync_status(
            child_text=variant["translations"].get(child_lang, ""),
            parent_text=variant["translations"].get(pivot_lang, ""),
            pivot_fingerprint_at_sync=sync_state["pivot_fingerprint_at_sync"],
        )
    return results


def test_variant_create_initializes_pivot_sync_rows_and_statuses() -> None:
    reset_db()
    project_id = create_pivot_project()
    entries = EntryService()
    catalog = VariantCatalogService()
    entry = entries.get_or_create_entry("pivot.entry", project_id=project_id)

    variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        catalog.build_content(
            "pivot.xlsx",
            "Hello",
            {"en": "Hello", "fr": "Bonjour", "de": ""},
            {"context": "pivot"},
        ),
    )

    sync_states = VariantPivotRepository().list_sync_states([variant_id])
    assert set(sync_states) == {(variant_id, "fr"), (variant_id, "de")}
    assert pivot_status_by_lang(project_id, variant_id) == {
        "fr": PIVOT_IN_SYNC,
        "de": MISSING_CHILD,
    }


def test_variant_parent_change_fans_out_and_child_update_resyncs_single_language() -> None:
    reset_db()
    project_id = create_pivot_project()
    entries = EntryService()
    catalog = VariantCatalogService()
    entry = entries.get_or_create_entry("pivot.entry", project_id=project_id)

    variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        catalog.build_content(
            "pivot.xlsx",
            "Hello",
            {"en": "Hello", "fr": "Bonjour", "de": "Hallo"},
            {"context": "pivot"},
        ),
    )

    catalog.update_variant(
        variant_id,
        catalog.build_content(
            "pivot.xlsx",
            "Hello",
            {"en": "Hello there", "fr": "Bonjour", "de": "Hallo"},
            {"context": "pivot"},
        ),
    )
    assert pivot_status_by_lang(project_id, variant_id) == {
        "fr": PIVOT_OUT_OF_SYNC,
        "de": PIVOT_OUT_OF_SYNC,
    }

    catalog.update_variant(
        variant_id,
        catalog.build_content(
            "pivot.xlsx",
            "Hello",
            {"en": "Hello there", "fr": "Bonjour a tous", "de": "Hallo"},
            {"context": "pivot"},
        ),
    )
    assert pivot_status_by_lang(project_id, variant_id) == {
        "fr": PIVOT_IN_SYNC,
        "de": PIVOT_OUT_OF_SYNC,
    }


def test_variant_missing_parent_and_parent_child_updates_transition_cleanly() -> None:
    reset_db()
    project_id = create_pivot_project()
    entries = EntryService()
    catalog = VariantCatalogService()
    entry = entries.get_or_create_entry("pivot.entry", project_id=project_id)

    variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        catalog.build_content(
            "pivot.xlsx",
            "Hello",
            {"en": "Hello", "fr": "Bonjour", "de": ""},
            {"context": "pivot"},
        ),
    )

    catalog.update_variant(
        variant_id,
        catalog.build_content(
            "pivot.xlsx",
            "Hello",
            {"en": "", "fr": "Bonjour", "de": ""},
            {"context": "pivot"},
        ),
    )
    assert pivot_status_by_lang(project_id, variant_id) == {
        "fr": MISSING_PARENT,
        "de": MISSING_PARENT,
    }

    catalog.update_variant(
        variant_id,
        catalog.build_content(
            "pivot.xlsx",
            "Hello",
            {"en": "Hello again", "fr": "Bonjour encore", "de": ""},
            {"context": "pivot"},
        ),
    )
    assert pivot_status_by_lang(project_id, variant_id) == {
        "fr": PIVOT_IN_SYNC,
        "de": MISSING_CHILD,
    }


def test_new_variant_source_gets_fresh_pivot_checkpoint() -> None:
    reset_db()
    project_id = create_pivot_project()
    entries = EntryService()
    catalog = VariantCatalogService()
    entry = entries.get_or_create_entry("pivot.entry", project_id=project_id)

    original_variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        catalog.build_content(
            "pivot.xlsx",
            "Hello",
            {"en": "Hello", "fr": "Bonjour", "de": "Hallo"},
            {"context": "pivot"},
        ),
    )
    catalog.update_variant(
        original_variant_id,
        catalog.build_content(
            "pivot.xlsx",
            "Hello",
            {"en": "Hello there", "fr": "Bonjour", "de": "Hallo"},
            {"context": "pivot"},
        ),
    )

    replacement_variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        catalog.build_content(
            "pivot-2.xlsx",
            "Hello v2",
            {"en": "Hello v2", "fr": "Bonjour v2", "de": "Hallo v2"},
            {"context": "pivot"},
        ),
    )

    assert pivot_status_by_lang(project_id, original_variant_id) == {
        "fr": PIVOT_OUT_OF_SYNC,
        "de": PIVOT_OUT_OF_SYNC,
    }
    assert pivot_status_by_lang(project_id, replacement_variant_id) == {
        "fr": PIVOT_IN_SYNC,
        "de": PIVOT_IN_SYNC,
    }
