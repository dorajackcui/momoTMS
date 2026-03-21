from pathlib import Path

from app.db import get_db_path
from app.services.branch.models import BranchRef
from app.services.branch.service import BranchService
from app.services.demo.service import DemoService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.variant.services import EntryService, ScopeBindingService, VariantCatalogService, VariantLifecycleService


def reset_demo() -> None:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    DemoService().reset()


def test_branch_ref_parsing_and_validation() -> None:
    assert str(BranchRef.parse("rel/current")) == "rel/current"
    assert str(BranchRef.dev("2.4.1")) == "dev/2.4.1"
    assert BranchRef.dev("2.4.1").version_series == "2.4.x"

    try:
        BranchRef.parse("rel/old")
    except ValueError as exc:
        assert "invalid release branch" in str(exc)
    else:
        raise AssertionError("expected invalid release branch")

    try:
        BranchRef.parse("dev/9.9.1")
    except ValueError as exc:
        assert "unsupported dev version series" in str(exc)
    else:
        raise AssertionError("expected unsupported dev version series")


def test_entry_variant_view_uses_variant_and_branch_ref_names() -> None:
    reset_demo()
    entries = EntryService()
    catalog = VariantCatalogService()
    bindings = ScopeBindingService()
    lifecycle = VariantLifecycleService()

    entry = entries.get_or_create_entry("view.entry", project_id=DEFAULT_PROJECT_ID)
    variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        "ui/messages.xlsx",
        "Hello",
        {"fr": "Bonjour"},
        {"context": "home"},
    )
    dev_variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        "ui/messages-dev.xlsx",
        "Hello dev",
        {"fr": "Bonjour dev"},
        {"context": "dev"},
    )
    bindings.bind_scope(int(entry["entry_id"]), BranchRef.rel_current(), variant_id)
    bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.1"), dev_variant_id)
    lifecycle.refresh_orphan_states(int(entry["entry_id"]))

    view = BranchService().list_branch_entries(BranchRef.rel_current(), DEFAULT_PROJECT_ID)
    item = next(row for row in view if row["business_key"] == "view.entry")
    assert item["variant_id"] == variant_id
    assert [binding["branch_ref"] for binding in item["bindings"]] == ["rel/current"]
    assert "memberships" not in item
    assert "string_id" not in item
