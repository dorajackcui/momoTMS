from pathlib import Path

from openpyxl import Workbook
import pytest

from app.db import get_conn, init_db
from app.services.branch.bootstrap import BranchBootstrapService
from app.services.branch.models import BranchRef
from app.services.branch.mutations import BranchMutationService
from app.services.bulk.writer import BulkVariantWriter
from app.services.project.service import ProjectService
from app.services.read_models.derived.branch_catalog import BranchCatalogView
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.workbooks.batches import WorkbookBatchService
from app.services.workbooks.models import WorkbookWorkflowContext


WORKBOOK_HEADERS = ["Key", "MsgStr", "en", "fr", "es", "Version", "SpeakerName"]


def write_workbook(root: Path, relative_path: str, rows: list[list[object]]) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(WORKBOOK_HEADERS)
    for row in rows:
        sheet.append(row)
    output_path = root / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    workbook.close()
    return output_path


def write_custom_workbook(
    root: Path,
    relative_path: str,
    headers: list[str],
    rows: list[list[object]],
) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output_path = root / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    workbook.close()
    return output_path


def branch_rows(branch_ref: BranchRef, project_id: int) -> dict[str, dict]:
    return {
        row["business_key"]: row
        for row in BranchCatalogView().list_branch_entries(branch_ref, project_id=project_id)
    }


def test_tdd_branch_cycle_release_bulk_seed_dev_bootstrap_then_translation_fill(tmp_path) -> None:
    init_db()
    project = ProjectService().create_project(
        "TDD Branch Cycle",
        ["en", "fr", "es"],
        ["Version", "SpeakerName"],
        pivot_language="en",
        pivoted_languages=["fr", "es"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])
    schema = ProjectService().get_schema(project_id)

    assert schema["translation_columns"] == ["en", "fr", "es"]
    assert schema["remark_columns"] == ["Version", "SpeakerName"]
    assert schema["pivot_language"] == "en"
    assert schema["pivoted_languages"] == ["fr", "es"]

    release_workbook = write_workbook(
        tmp_path / "release",
        "2.4diff3.xlsx",
        [
            ["cycle.same", "Shared source", "Shared source", "FR rel same", "ES rel same", "2.4", "RelSpeaker"],
            ["cycle.changed", "Rel source", "Rel source", "FR rel old", "ES rel old", "2.4", "Narrator"],
        ],
    )
    release_seed = BulkVariantWriter().seed(
        project_id=project_id,
        branch_ref=BranchRef.rel_current(),
        workbook_path=str(release_workbook),
    )

    assert release_seed["entries_created"] == 2
    assert release_seed["variants_created"] == 2
    assert release_seed["bindings_created"] == 2
    assert set(branch_rows(BranchRef.rel_current(), project_id)) == {"cycle.same", "cycle.changed"}

    dev_root = tmp_path / "dev"
    write_workbook(
        dev_root,
        "2.5diff3.xlsx",
        [
            ["cycle.same", "Shared source", "Shared source edited", "FR dev filtered", "ES dev filtered", "2.5", "DevSpeaker"],
            ["cycle.changed", "Dev source", "Dev source", "FR dev changed", "ES dev changed", "2.5", "Narrator"],
            ["cycle.new", "New source", "New source", "FR dev new", "ES dev new", "2.5", "NewSpeaker"],
        ],
    )

    dev_ref = BranchRef.dev("2.5.3")
    bootstrap_batch = WorkbookBatchService().create_batch_from_directory(
        dev_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="create_branch"),
    )
    bootstrap = BranchBootstrapService().bootstrap(
        dev_ref,
        bootstrap_batch["workbook_batch_id"],
        project_id=project_id,
    )
    bootstrap_rows = {row["business_key"]: row for row in bootstrap["report_rows"]}

    assert bootstrap["summary"]["processed_count"] == 3
    assert bootstrap["summary"]["bound_existing_variant_count"] == 1
    assert bootstrap["summary"]["created_and_bound_variant_count"] == 2
    assert bootstrap["summary"]["created_entry_count"] == 1
    assert bootstrap["summary"]["created_variant_count"] == 2
    assert bootstrap_rows["cycle.same"]["status"] == "BOUND_EXISTING_VARIANT"
    assert bootstrap_rows["cycle.changed"]["status"] == "CREATED_AND_BOUND_VARIANT"
    assert bootstrap_rows["cycle.new"]["status"] == "CREATED_AND_BOUND_VARIANT"

    catalog = VariantCatalogService()
    dev_after_bootstrap = branch_rows(dev_ref, project_id)
    same_after_bootstrap = catalog.get_variant(int(dev_after_bootstrap["cycle.same"]["variant_id"]))
    changed_after_bootstrap = catalog.get_variant(int(dev_after_bootstrap["cycle.changed"]["variant_id"]))
    new_after_bootstrap = catalog.get_variant(int(dev_after_bootstrap["cycle.new"]["variant_id"]))

    assert same_after_bootstrap["translations"]["fr"] == "FR rel same"
    assert same_after_bootstrap["remarks"] == {"Version": "2.4", "SpeakerName": "RelSpeaker"}
    assert changed_after_bootstrap["translations"] == {}
    assert changed_after_bootstrap["remarks"] == {"Version": "2.5", "SpeakerName": "Narrator"}
    assert new_after_bootstrap["translations"] == {}
    assert new_after_bootstrap["remarks"] == {"Version": "2.5", "SpeakerName": "NewSpeaker"}

    content_batch = WorkbookBatchService().create_batch_from_directory(
        dev_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )
    mutation = BranchMutationService().apply(
        dev_ref,
        {
            "kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": content_batch["workbook_batch_id"],
        },
        project_id=project_id,
    )
    mutation_rows = {row["business_key"]: row for row in mutation["report_rows"]}

    assert mutation["summary"]["processed_count"] == 3
    assert mutation["summary"]["updated_bound_variant_count"] == 2
    assert mutation["summary"]["noop_count"] == 1
    assert mutation["summary"]["content_filtered_by_authority_count"] == 1
    assert mutation_rows["cycle.same"]["status"] == "NOOP"
    assert mutation_rows["cycle.same"]["content_filtered_by_authority"] is True
    assert mutation_rows["cycle.changed"]["status"] == "UPDATED_BOUND_VARIANT"
    assert mutation_rows["cycle.new"]["status"] == "UPDATED_BOUND_VARIANT"

    dev_after_content = branch_rows(dev_ref, project_id)
    same_variant = catalog.get_variant(int(dev_after_content["cycle.same"]["variant_id"]))
    changed_variant = catalog.get_variant(int(dev_after_content["cycle.changed"]["variant_id"]))
    new_variant = catalog.get_variant(int(dev_after_content["cycle.new"]["variant_id"]))

    assert same_variant["translations"]["fr"] == "FR rel same"
    assert same_variant["remarks"]["Version"] == "2.4"
    assert same_variant["pivot_status"] == "init"

    assert changed_variant["translations"] == {
        "en": "Dev source",
        "fr": "FR dev changed",
        "es": "ES dev changed",
    }
    assert changed_variant["remarks"] == {"Version": "2.5", "SpeakerName": "Narrator"}
    assert changed_variant["pivot_status"] == "init"
    assert changed_variant["pivot_changed_by_scope_type"] is None
    assert changed_variant["pivot_changed_by_scope_value"] is None

    assert new_variant["translations"] == {
        "en": "New source",
        "fr": "FR dev new",
        "es": "ES dev new",
    }
    assert new_variant["remarks"] == {"Version": "2.5", "SpeakerName": "NewSpeaker"}
    assert new_variant["pivot_status"] == "init"
    assert new_variant["pivot_changed_by_scope_type"] is None
    assert new_variant["pivot_changed_by_scope_value"] is None


def test_tdd_first_pivot_language_write_on_bare_variant_remains_init() -> None:
    init_db()
    project = ProjectService().create_project(
        "TDD Pivot First Write",
        ["en", "fr"],
        ["Note"],
        pivot_language="en",
        pivoted_languages=["fr"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])
    entry = EntryService().get_or_create_entry("pivot.first.write", project_id=project_id)
    catalog = VariantCatalogService()
    variant_id = catalog.create_variant_bare(
        int(entry["entry_id"]),
        "Source",
        file_name="first-write.xlsx",
    )

    catalog.update_variant(
        variant_id,
        catalog.build_content(
            "first-write.xlsx",
            "Source",
            {"en": "First English", "fr": "Premier francais"},
            {"Note": ""},
        ),
        actor_scope=BranchRef.dev("2.5.3").as_tuple(),
    )

    variant = catalog.get_variant(variant_id)
    assert variant["translations"]["en"] == "First English"
    assert variant["pivot_status"] == "init"
    assert variant["pivot_changed_by_scope_type"] is None
    assert variant["pivot_changed_by_scope_value"] is None
    assert variant["pivot_changed_at"] is None


def test_tdd_content_mutation_uses_schema_fields_clears_blanks_and_ignores_extra_columns(tmp_path) -> None:
    init_db()
    project = ProjectService().create_project(
        "TDD Content Sparse",
        ["en", "fr", "es"],
        ["Version", "SpeakerName"],
        pivot_language="en",
        pivoted_languages=["fr", "es"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])

    release_workbook = write_workbook(
        tmp_path / "release",
        "2.4diff3.xlsx",
        [
            ["content.same", "Shared source", "Shared source", "FR rel", "ES rel", "2.4", "RelSpeaker"],
            ["content.dev", "Old source", "Old EN", "Old FR", "Old ES", "2.4", "OldSpeaker"],
        ],
    )
    BulkVariantWriter().seed(
        project_id=project_id,
        branch_ref=BranchRef.rel_current(),
        workbook_path=str(release_workbook),
    )

    dev_ref = BranchRef.dev("2.5.3")
    bootstrap_root = tmp_path / "bootstrap"
    write_workbook(
        bootstrap_root,
        "2.5diff3.xlsx",
        [
            ["content.same", "Shared source", "Shared source edited", "FR filtered", "ES filtered", "2.5", "DevSpeaker"],
            ["content.dev", "Dev source", "New EN", "", "New ES", "", "NewSpeaker"],
        ],
    )
    bootstrap_batch = WorkbookBatchService().create_batch_from_directory(
        bootstrap_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="create_branch"),
    )
    BranchBootstrapService().bootstrap(dev_ref, bootstrap_batch["workbook_batch_id"], project_id=project_id)

    baseline_content_root = tmp_path / "baseline-content"
    write_workbook(
        baseline_content_root,
        "2.5full-content.xlsx",
        [
            ["content.dev", "Dev source", "Baseline EN", "Baseline FR", "New ES", "2.5", "BaselineSpeaker"],
        ],
    )
    baseline_content_batch = WorkbookBatchService().create_batch_from_directory(
        baseline_content_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )
    BranchMutationService().apply(
        dev_ref,
        {
            "kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": baseline_content_batch["workbook_batch_id"],
        },
        project_id=project_id,
    )

    content_root = tmp_path / "content"
    write_custom_workbook(
        content_root,
        "2.5content.xlsx",
        ["Key", "MsgStr", "en", "fr", "Version", "SpeakerName", "TranslatorNote"],
        [
            ["content.same", "Shared source", "Blocked EN", "Blocked FR", "2.5", "BlockedSpeaker", "ignored"],
            ["content.dev", "Dev source", "New EN", "", "", "NewSpeaker", "ignored"],
        ],
    )
    content_batch = WorkbookBatchService().create_batch_from_directory(
        content_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )

    mutation = BranchMutationService().apply(
        dev_ref,
        {
            "kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": content_batch["workbook_batch_id"],
        },
        project_id=project_id,
    )

    rows = {row["business_key"]: row for row in mutation["report_rows"]}
    assert mutation["summary"]["processed_count"] == 2
    assert mutation["summary"]["updated_bound_variant_count"] == 1
    assert mutation["summary"]["noop_count"] == 1
    assert mutation["summary"]["content_filtered_by_authority_count"] == 1
    assert rows["content.same"]["status"] == "NOOP"
    assert rows["content.same"]["content_filtered_by_authority"] is True
    assert rows["content.dev"]["status"] == "UPDATED_BOUND_VARIANT"

    catalog = VariantCatalogService()
    dev_rows = branch_rows(dev_ref, project_id)
    same_variant = catalog.get_variant(int(dev_rows["content.same"]["variant_id"]))
    dev_variant = catalog.get_variant(int(dev_rows["content.dev"]["variant_id"]))

    assert same_variant["translations"]["en"] == "Shared source"
    assert same_variant["translations"]["fr"] == "FR rel"
    assert same_variant["remarks"]["Version"] == "2.4"
    assert same_variant["remarks"]["SpeakerName"] == "RelSpeaker"
    assert "TranslatorNote" not in same_variant["remarks"]

    assert dev_variant["translations"]["en"] == "New EN"
    assert dev_variant["translations"]["fr"] == ""
    assert dev_variant["translations"]["es"] == "New ES"
    assert dev_variant["remarks"]["Version"] == ""
    assert dev_variant["remarks"]["SpeakerName"] == "NewSpeaker"
    assert "TranslatorNote" not in dev_variant["remarks"]
    assert dev_variant["pivot_status"] == "changed"
    assert dev_variant["pivot_changed_by_scope_type"] == "dev"
    assert dev_variant["pivot_changed_by_scope_value"] == "2.5.3"


def test_tdd_content_mutation_preserves_duplicate_key_row_order_within_batch(tmp_path) -> None:
    init_db()
    project = ProjectService().create_project(
        "TDD Content Duplicate Order",
        ["en", "fr"],
        ["Note"],
        pivot_language="en",
        pivoted_languages=["fr"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])
    dev_ref = BranchRef.dev("2.5.3")

    bootstrap_root = tmp_path / "bootstrap"
    write_custom_workbook(
        bootstrap_root,
        "bootstrap.xlsx",
        ["Key", "MsgStr", "en", "fr"],
        [["dup.key", "Dup source", "ignored", "ignored"]],
    )
    bootstrap_batch = WorkbookBatchService().create_batch_from_directory(
        bootstrap_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="create_branch"),
    )
    BranchBootstrapService().bootstrap(dev_ref, bootstrap_batch["workbook_batch_id"], project_id=project_id)

    content_root = tmp_path / "content"
    write_custom_workbook(
        content_root,
        "content.xlsx",
        ["Key", "MsgStr", "en", "fr"],
        [
            ["dup.key", "Dup source", "Dup source", "FR interim"],
            ["dup.key", "Dup source", "Dup source", "FR final"],
            ["dup.key", "Dup source", "Dup source", "FR final"],
        ],
    )
    content_batch = WorkbookBatchService().create_batch_from_directory(
        content_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )
    mutation = BranchMutationService().apply(
        dev_ref,
        {
            "kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": content_batch["workbook_batch_id"],
        },
        project_id=project_id,
    )

    assert [row["status"] for row in mutation["report_rows"]] == [
        "UPDATED_BOUND_VARIANT",
        "UPDATED_BOUND_VARIANT",
        "NOOP",
    ]
    assert mutation["summary"]["updated_bound_variant_count"] == 2
    assert mutation["summary"]["noop_count"] == 1

    variant_id = int(branch_rows(dev_ref, project_id)["dup.key"]["variant_id"])
    variant = VariantCatalogService().get_variant(variant_id)
    assert variant["translations"] == {"en": "Dup source", "fr": "FR final"}


def test_tdd_content_mutation_reports_progress_and_stage_timing(tmp_path) -> None:
    init_db()
    project = ProjectService().create_project(
        "TDD Content Progress",
        ["en", "fr", "es"],
        ["Version", "SpeakerName"],
        pivot_language="en",
        pivoted_languages=["fr", "es"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])

    release_workbook = write_workbook(
        tmp_path / "release",
        "2.4diff3.xlsx",
        [["progress.key", "Old source", "Old source", "FR old", "ES old", "2.4", "Speaker"]],
    )
    BulkVariantWriter().seed(
        project_id=project_id,
        branch_ref=BranchRef.rel_current(),
        workbook_path=str(release_workbook),
    )

    dev_ref = BranchRef.dev("2.5.3")
    dev_root = tmp_path / "dev"
    write_workbook(
        dev_root,
        "2.5diff3.xlsx",
        [["progress.key", "New source", "New source", "FR new", "ES new", "2.5", "Speaker"]],
    )
    bootstrap_batch = WorkbookBatchService().create_batch_from_directory(
        dev_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="create_branch"),
    )
    BranchBootstrapService().bootstrap(dev_ref, bootstrap_batch["workbook_batch_id"], project_id=project_id)

    content_batch = WorkbookBatchService().create_batch_from_directory(
        dev_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )
    progress_payloads: list[dict] = []
    with get_conn() as conn:
        result = BranchMutationService().content_batch.apply(
            dev_ref,
            int(content_batch["workbook_batch_id"]),
            project_id,
            conn=conn,
            progress_callback=progress_payloads.append,
            progress_interval=1,
            max_elapsed_seconds=300,
        )

    assert progress_payloads
    assert progress_payloads[-1]["processed_count"] == 1
    assert result["summary"]["processed_count"] == 1
    assert result["summary"]["stages"][0]["stage"] == "apply_content_mutation"
    assert result["summary"]["stages"][0]["meta"]["processed_count"] == 1


def test_tdd_content_mutation_raises_when_bound_variant_row_is_missing(tmp_path) -> None:
    init_db()
    project = ProjectService().create_project(
        "TDD Content Dangling Binding",
        ["en", "fr"],
        ["Note"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])
    dev_ref = BranchRef.dev("2.5.3")

    bootstrap_root = tmp_path / "bootstrap"
    write_custom_workbook(
        bootstrap_root,
        "bootstrap.xlsx",
        ["Key", "MsgStr", "en", "fr"],
        [["dangling.key", "Dangling source", "ignored", "ignored"]],
    )
    bootstrap_batch = WorkbookBatchService().create_batch_from_directory(
        bootstrap_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="create_branch"),
    )
    BranchBootstrapService().bootstrap(dev_ref, bootstrap_batch["workbook_batch_id"], project_id=project_id)

    content_root = tmp_path / "content"
    write_custom_workbook(
        content_root,
        "content.xlsx",
        ["Key", "MsgStr", "en", "fr"],
        [["dangling.key", "Dangling source", "Dangling source", "Updated FR"]],
    )
    content_batch = WorkbookBatchService().create_batch_from_directory(
        content_root,
        project_id,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )

    variant_id = int(branch_rows(dev_ref, project_id)["dangling.key"]["variant_id"])
    with get_conn() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DELETE FROM variants WHERE variant_id = ?", (variant_id,))
        conn.execute("PRAGMA foreign_keys = ON")

    with pytest.raises(KeyError, match=f"variant not found: {variant_id}"):
        BranchMutationService().apply(
            dev_ref,
            {
                "kind": "workbook_batch",
                "mutation_type": "content",
                "workbook_batch_id": content_batch["workbook_batch_id"],
            },
            project_id=project_id,
        )
