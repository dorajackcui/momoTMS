import sqlite3
from pathlib import Path

from app.services.branch.mutations import BranchMutationService
from app.services.branch.models import BranchRef
from app.services.project.bootstrap import ProjectBootstrapService
from app.services.demo.service import DemoService
from app.services.imports.service import ImportService
from app.services.read_models.derived.branch_summary import BranchSummaryView
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.lifecycle import VariantLifecycleService
from app.services.variant.state_coordinator import VariantStateCoordinator
from tests.service_helpers import branch_services
from app.db import get_db_path


def reset_demo() -> None:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    DemoService().reset()


def count_sql_queries(run):
    original_connect = sqlite3.connect
    counter = {"count": 0}

    def traced_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)

        def trace(sql: str) -> None:
            statement = sql.strip().upper()
            if statement.startswith(("BEGIN", "COMMIT", "ROLLBACK", "PRAGMA")):
                return
            counter["count"] += 1

        conn.set_trace_callback(trace)
        return conn

    sqlite3.connect = traced_connect
    try:
        result = run()
    finally:
        sqlite3.connect = original_connect
    return counter["count"], result


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
    bindings = VariantStateCoordinator()
    lifecycle = VariantLifecycleService()

    entry = entries.get_or_create_entry("view.entry", project_id=DEFAULT_PROJECT_ID)
    variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        catalog.build_content(
            "ui/messages.xlsx",
            "Hello",
            {"fr": "Bonjour"},
            {"context": "home"},
        ),
    )
    dev_variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        catalog.build_content(
            "ui/messages-dev.xlsx",
            "Hello dev",
            {"fr": "Bonjour dev"},
            {"context": "dev"},
        ),
    )
    bindings.bind_scope(int(entry["entry_id"]), BranchRef.rel_current(), variant_id)
    bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.1"), dev_variant_id)
    lifecycle.refresh_orphan_states(int(entry["entry_id"]))

    view = branch_services().list_branch_entries(BranchRef.rel_current(), DEFAULT_PROJECT_ID)
    item = next(row for row in view if row["business_key"] == "view.entry")
    assert item["variant_id"] == variant_id
    assert [binding["branch_ref"] for binding in item["bindings"]] == ["rel/current"]
    assert "memberships" not in item
    assert "string_id" not in item


def test_project_state_query_budget_with_active_dev_branch() -> None:
    reset_demo()
    sample = DemoService().get_sample("core-cycle")
    batch = ImportService().import_directory(sample["paths"]["import_dir"])
    BranchMutationService().apply(
        BranchRef.dev(sample["dev_version"]),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
            "mark_as_candidate_release": True,
        },
    )

    query_count, state = count_sql_queries(lambda: ProjectBootstrapService().get_state(DEFAULT_PROJECT_ID))

    assert state["release_summary"]["branch_ref"] == "rel/current"
    assert state["candidate_dev_branch"] is not None
    assert state["candidate_dev_branch"]["branch_ref"] == f"dev/{sample['dev_version']}"
    assert state["dev_branches"][0]["branch_ref"] == f"dev/{sample['dev_version']}"
    assert query_count <= 12


def test_branch_summary_query_budget_with_active_dev_branch() -> None:
    reset_demo()
    sample = DemoService().get_sample("core-cycle")
    batch = ImportService().import_directory(sample["paths"]["import_dir"])
    BranchMutationService().apply(
        BranchRef.dev(sample["dev_version"]),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
            "mark_as_candidate_release": True,
        },
    )

    query_count, summary = count_sql_queries(lambda: BranchSummaryView().build(DEFAULT_PROJECT_ID, lang="fr"))
    branches = {item["branch_ref"]: item for item in summary["branches"]}

    assert "rel/current" in branches
    assert f"dev/{sample['dev_version']}" in branches
    assert branches[f"dev/{sample['dev_version']}"]["is_candidate_release"] is True
    assert query_count <= 3
