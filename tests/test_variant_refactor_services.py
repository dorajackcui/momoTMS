from pathlib import Path

from app.db import get_db_path
from app.services.demo.service import DemoService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.variant.repositories import VariantRepository
from app.services.variant.services import (
    EntryService,
    PreferredEntryViewService,
    ScopeBindingService,
    VariantCatalogService,
    VariantLifecycleService,
)


def reset_demo() -> None:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    DemoService().reset()


def test_variant_repository_hydrates_nested_content() -> None:
    reset_demo()
    entries = EntryService()
    catalog = VariantCatalogService()
    repository = VariantRepository()

    entry = entries.get_or_create_entry("repo.hydrated", project_id=DEFAULT_PROJECT_ID)
    variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        " ui/messages.xlsx ",
        " Hello ",
        {"fr": "  Bonjour  ", "en": "Hello"},
        {"context": "  home  "},
    )

    grouped = repository.list_by_entries([int(entry["entry_id"])], include_trashed=False)
    hydrated = grouped[int(entry["entry_id"])][0]

    assert hydrated["variant_id"] == variant_id
    assert hydrated["file_name"] == "ui/messages.xlsx"
    assert hydrated["source"] == "Hello"
    assert hydrated["translations"]["fr"] == "  Bonjour  "
    assert hydrated["remarks"]["context"] == "home"


def test_preferred_entry_view_selection_order() -> None:
    reset_demo()
    entries = EntryService()
    catalog = VariantCatalogService()
    bindings = ScopeBindingService()
    lifecycle = VariantLifecycleService()
    views = PreferredEntryViewService(entries, catalog, bindings, lifecycle)

    rel_entry = entries.get_or_create_entry("preferred.rel", project_id=DEFAULT_PROJECT_ID)
    rel_variant_id = catalog.create_variant(int(rel_entry["entry_id"]), None, "Release", {"fr": "Rel"}, {})
    dev_variant_id = catalog.create_variant(int(rel_entry["entry_id"]), None, "Dev", {"fr": "Dev"}, {})
    bindings.bind_scope(int(rel_entry["entry_id"]), "dev", "2.0.0", dev_variant_id)
    bindings.bind_scope(int(rel_entry["entry_id"]), "rel", "current", rel_variant_id)

    dev_entry = entries.get_or_create_entry("preferred.dev", project_id=DEFAULT_PROJECT_ID)
    newer_dev_variant_id = catalog.create_variant(int(dev_entry["entry_id"]), None, "Dev B", {"fr": "B"}, {})
    older_dev_variant_id = catalog.create_variant(int(dev_entry["entry_id"]), None, "Dev A", {"fr": "A"}, {})
    bindings.bind_scope(int(dev_entry["entry_id"]), "dev", "2.0.0", newer_dev_variant_id)
    bindings.bind_scope(int(dev_entry["entry_id"]), "dev", "1.0.0", older_dev_variant_id)

    orphan_entry = entries.get_or_create_entry("preferred.orphan", project_id=DEFAULT_PROJECT_ID)
    orphan_variant_id = catalog.create_variant(int(orphan_entry["entry_id"]), None, "Orphan", {"fr": "Keep"}, {})
    lifecycle.refresh_orphan_states(int(orphan_entry["entry_id"]))

    latest_entry = entries.get_or_create_entry("preferred.latest", project_id=DEFAULT_PROJECT_ID)
    older_variant_id = catalog.create_variant(int(latest_entry["entry_id"]), None, "Older", {"fr": "Older"}, {})
    latest_variant_id = catalog.create_variant(int(latest_entry["entry_id"]), None, "Latest", {"fr": "Latest"}, {})
    lifecycle.refresh_orphan_states(int(latest_entry["entry_id"]))

    assert views.get_preferred_entry_view("preferred.rel", DEFAULT_PROJECT_ID)["string_id"] == rel_variant_id
    assert views.get_preferred_entry_view("preferred.dev", DEFAULT_PROJECT_ID)["string_id"] == older_dev_variant_id
    assert views.get_preferred_entry_view("preferred.orphan", DEFAULT_PROJECT_ID)["string_id"] == orphan_variant_id
    assert views.get_preferred_entry_view("preferred.latest", DEFAULT_PROJECT_ID)["string_id"] == latest_variant_id
    assert older_variant_id != latest_variant_id


def test_scope_rebind_orphans_previous_variant_and_trash_restore_round_trip() -> None:
    reset_demo()
    entries = EntryService()
    catalog = VariantCatalogService()
    bindings = ScopeBindingService()
    lifecycle = VariantLifecycleService()
    views = PreferredEntryViewService(entries, catalog, bindings, lifecycle)

    entry = entries.get_or_create_entry("lifecycle.roundtrip", project_id=DEFAULT_PROJECT_ID)
    first_variant_id = catalog.create_variant(int(entry["entry_id"]), None, "Initial", {"fr": "A"}, {})
    second_variant_id = catalog.create_variant(int(entry["entry_id"]), None, "Replacement", {"fr": "B"}, {})

    bindings.bind_scope(int(entry["entry_id"]), "rel", "current", first_variant_id)
    bindings.bind_scope(int(entry["entry_id"]), "rel", "current", second_variant_id)

    assert catalog.get_variant(first_variant_id)["orphaned_at"] is not None

    delete_result = lifecycle.trash_entries(["lifecycle.roundtrip"], project_id=DEFAULT_PROJECT_ID, trash_days=30)
    assert delete_result["deleted"] == ["lifecycle.roundtrip"]
    trashed_view = views.get_preferred_entry_view("lifecycle.roundtrip", DEFAULT_PROJECT_ID)
    assert trashed_view is not None
    assert trashed_view["deleted_at"] is not None

    restore_result = lifecycle.restore_entries(["lifecycle.roundtrip"], project_id=DEFAULT_PROJECT_ID)
    assert restore_result["restored"] == ["lifecycle.roundtrip"]
    restored_view = views.get_preferred_entry_view("lifecycle.roundtrip", DEFAULT_PROJECT_ID)
    assert restored_view is not None
    assert restored_view["deleted_at"] is None
    assert restored_view["restored_at"] is not None
