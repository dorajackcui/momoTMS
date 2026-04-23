from pathlib import Path

import pytest
from openpyxl import Workbook

from app.db import get_db_path
from app.services.branch.bootstrap import BranchBootstrapService
from app.services.branch.models import BranchRef
from app.services.branch.mutations import BranchMutationService
from app.services.branch.policy import AuthorityPolicy
from app.services.branch.preview_contract import EffectPreviewSummaryBuilder
from app.services.branch.replace import BranchReplaceService
from app.services.branch.registry import BranchRegistryService
from app.services.demo.service import DemoService
from app.services.imports.service import ImportService
from app.services.read_models.datasets.entry_timeline import EntryTimelineDataset
from app.services.workflows.trash_restore import TrashRestoreService
from tests.service_helpers import branch_services


def test_branch_ref_orphan_factory_and_properties() -> None:
    ref = BranchRef.orphan()
    assert str(ref) == "orphan"
    assert ref.is_orphan is True
    assert ref.is_rel is False
    assert ref.is_dev is False
    assert ref.version is None
    assert ref.version_series is None
    assert ref.version_parts is None


def test_branch_ref_orphan_parse_round_trip() -> None:
    ref = BranchRef.parse("orphan")
    assert ref.is_orphan is True
    assert str(ref) == "orphan"


def test_branch_ref_orphan_as_tuple_raises() -> None:
    ref = BranchRef.orphan()
    with pytest.raises(ValueError, match="orphan branch cannot be used as a scope binding"):
        ref.as_tuple()


def reset_demo() -> dict:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    DemoService().reset()
    return DemoService().get_sample("core-cycle")


def write_import_workbook(root: Path, relative_path: str, rows: list[list[object]]) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    for row in rows:
        sheet.append(row)
    output_path = root / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    workbook.close()
    return output_path


def test_bootstrap_reuses_existing_variant_and_ignores_uploaded_content(tmp_path) -> None:
    sample = reset_demo()
    read_service = branch_services()
    existing_entry = next(
        item for item in read_service.list_branch_entries(BranchRef.rel_current()) if item["business_key"] == "rel.locked.same"
    )
    existing_variant_id = existing_entry["variant_id"]
    existing_variant = read_service.catalog.get_variant(existing_variant_id)
    expected_translations = dict(existing_variant["translations"])
    expected_remarks = dict(existing_variant["remarks"])
    expected_file_name = existing_variant["file_name"]

    import_root = tmp_path / "bootstrap-reuse"
    write_import_workbook(
        import_root,
        "bundle/bootstrap-reuse.xlsx",
        [
            ["business_key", "source", "fr", "context"],
            ["rel.locked.same", existing_variant["source"], "Uploaded override", "Uploaded override"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = BranchBootstrapService().bootstrap(BranchRef.dev(sample["dev_version"]), batch["import_batch_id"])
    row = next(item for item in result["report_rows"] if item["business_key"] == "rel.locked.same")
    bootstrapped_entry = next(
        item for item in read_service.list_branch_entries(BranchRef.dev(sample["dev_version"])) if item["business_key"] == "rel.locked.same"
    )
    reused_variant = read_service.catalog.get_variant(existing_variant_id)
    branch_metadata = read_service.get_dev_branch(sample["dev_version"])

    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert bootstrapped_entry["variant_id"] == existing_variant_id
    assert reused_variant["translations"] == expected_translations
    assert reused_variant["remarks"] == expected_remarks
    assert reused_variant["file_name"] == expected_file_name
    assert branch_metadata["bootstrap_state"] == "bootstrapped"
    assert branch_metadata["bootstrap_import_batch_id"] == batch["import_batch_id"]
    assert branch_metadata["bootstrap_job_id"] is not None


def test_bootstrap_reports_duplicate_keys_and_invalid_rows_without_aborting_job(tmp_path) -> None:
    sample = reset_demo()
    read_service = branch_services()
    import_root = tmp_path / "bootstrap-invalid"
    write_import_workbook(
        import_root,
        "bundle/bootstrap-invalid.xlsx",
        [
            ["business_key", "source", "fr", "context"],
            ["bootstrap.good", "Bootstrap source", "Bonjour good", "good"],
            ["bootstrap.good", "Bootstrap source", "Bonjour duplicate", "duplicate"],
            ["", "Blank key source", "Bonjour blank key", "blank-key"],
            ["bootstrap.blank.source", "", "Bonjour blank source", "blank-source"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = BranchBootstrapService().bootstrap(BranchRef.dev(sample["dev_version"]), batch["import_batch_id"])
    statuses = [item["status"] for item in result["report_rows"]]
    dev_entries = read_service.list_branch_entries(BranchRef.dev(sample["dev_version"]))
    branch_metadata = read_service.get_dev_branch(sample["dev_version"])

    assert result["summary"]["processed_count"] == 4
    assert statuses.count("CREATED_AND_BOUND_VARIANT") == 1
    assert statuses.count("DUPLICATE_KEY_IN_BOOTSTRAP") == 1
    assert statuses.count("INVALID_ROW") == 2
    assert sum(1 for item in dev_entries if item["business_key"] == "bootstrap.good") == 1
    assert any(item["business_key"] == "bootstrap.good" for item in dev_entries)
    assert not any(item["business_key"] == "" for item in dev_entries)
    assert not any(item["business_key"] == "bootstrap.blank.source" for item in dev_entries)
    assert branch_metadata["bootstrap_state"] == "bootstrapped"
    assert branch_metadata["bootstrap_import_batch_id"] == batch["import_batch_id"]
    assert branch_metadata["bootstrap_job_id"] is not None


def test_bootstrap_rejects_branch_that_is_already_bootstrapped(tmp_path) -> None:
    sample = reset_demo()
    import_root = tmp_path / "bootstrap-repeat"
    write_import_workbook(
        import_root,
        "bundle/bootstrap-repeat.xlsx",
        [
            ["business_key", "source", "fr"],
            ["bootstrap.repeat", "Bootstrap source", "Bonjour bootstrap"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))
    bootstrap_service = BranchBootstrapService()

    first_result = bootstrap_service.bootstrap(BranchRef.dev(sample["dev_version"]), batch["import_batch_id"])
    branch_metadata_before = branch_services().get_dev_branch(sample["dev_version"])

    assert first_result["report_rows"][0]["status"] == "CREATED_AND_BOUND_VARIANT"
    assert branch_metadata_before["bootstrap_state"] == "bootstrapped"
    assert branch_metadata_before["bootstrap_import_batch_id"] == batch["import_batch_id"]
    assert branch_metadata_before["bootstrap_job_id"] is not None

    with pytest.raises(ValueError, match="already bootstrapped"):
        bootstrap_service.bootstrap(BranchRef.dev(sample["dev_version"]), batch["import_batch_id"])

    branch_metadata_after = branch_services().get_dev_branch(sample["dev_version"])
    assert branch_metadata_after == branch_metadata_before


def test_bootstrap_processes_bind_heavy_rows_across_chunk_boundary(tmp_path) -> None:
    sample = reset_demo()
    read_service = branch_services()
    for index in range(1005):
        business_key = f"bootstrap.chunk.{index:04d}"
        entry = read_service.entries.get_or_create_entry(business_key, project_id=1)
        variant_id = read_service.catalog.create_variant(
            int(entry["entry_id"]),
            read_service.catalog.build_content(
                f"{business_key}.xlsx",
                f"Shared source {index}",
                {"fr": f"Existing text {index}"},
                {"context": f"Existing context {index}"},
            ),
        )
        read_service.bindings.bind(int(entry["entry_id"]), BranchRef.rel_current(), variant_id)

    import_root = tmp_path / "bootstrap-chunk-boundary"
    rows: list[list[object]] = [["business_key", "source", "fr", "context"]]
    for index in range(1005):
        business_key = f"bootstrap.chunk.{index:04d}"
        rows.append(
            [
                business_key,
                f"Shared source {index}",
                f"Uploaded text {index}",
                f"Uploaded context {index}",
            ]
        )
    write_import_workbook(
        import_root,
        "bundle/bootstrap-chunk-boundary.xlsx",
        rows,
    )
    batch = ImportService().import_directory(str(import_root))

    result = BranchBootstrapService().bootstrap(BranchRef.dev(sample["dev_version"]), batch["import_batch_id"])
    rows = result["report_rows"]
    row_by_key = {item["business_key"]: item for item in rows}
    row_keys = [item["business_key"] for item in rows]
    expected_keys = {f"bootstrap.chunk.{index:04d}" for index in range(1005)}

    assert result["summary"]["processed_count"] == 1005
    assert result["summary"]["bound_existing_variant_count"] == 1005
    assert result["summary"]["created_and_bound_variant_count"] == 0
    assert len(rows) == 1005
    assert len(row_by_key) == 1005
    assert set(row_keys) == expected_keys
    assert all(item["status"] == "BOUND_EXISTING_VARIANT" for item in rows)


def test_bootstrap_preview_reports_reuse_create_invalid_and_duplicate_rows_without_writes(tmp_path) -> None:
    sample = reset_demo()
    read_service = branch_services()
    existing_row = next(
        item
        for item in read_service.list_branch_entries(BranchRef.rel_current())
        if item["business_key"] == "rel.locked.same"
    )
    BranchRegistryService().ensure_dev_branch(sample["dev_version"], project_id=1)
    branch_metadata_before = read_service.get_dev_branch(sample["dev_version"])

    import_root = tmp_path / "bootstrap-preview"
    write_import_workbook(
        import_root,
        "bundle/bootstrap-preview.xlsx",
        [
            ["business_key", "source", "fr", "context"],
            ["rel.locked.same", existing_row["source"], "Uploaded reuse", "reuse"],
            ["bootstrap.preview.new", "Preview source", "Uploaded create", "create"],
            ["", "Broken source", "Uploaded invalid", "invalid"],
            ["bootstrap.preview.new", "Preview source", "Uploaded duplicate", "duplicate"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    preview = BranchBootstrapService().preview(BranchRef.dev(sample["dev_version"]), batch["import_batch_id"])
    rows = preview["rows"]
    statuses = [row["status"] for row in rows]
    branch_metadata_after = read_service.get_dev_branch(sample["dev_version"])

    assert preview["preview_kind"] == "effect_forecast"
    assert preview["workflow_kind"] == "branch_bootstrap"
    assert preview["request_echo"] == {
        "branch_ref": f"dev/{sample['dev_version']}",
        "import_batch_id": batch["import_batch_id"],
    }
    assert statuses == [
        "BOUND_EXISTING_VARIANT",
        "CREATED_AND_BOUND_VARIANT",
        "INVALID_ROW",
        "DUPLICATE_KEY_IN_BOOTSTRAP",
    ]
    assert rows[0]["binding_effect"] == "bind"
    assert rows[0]["variant_resolution"] == "reuse_existing"
    assert rows[0]["row_outcome"] == "applied"
    assert rows[1]["binding_effect"] == "bind"
    assert rows[1]["variant_resolution"] == "create_new"
    assert rows[1]["row_outcome"] == "applied"
    assert rows[2]["binding_effect"] == "none"
    assert rows[2]["variant_resolution"] == "stay_current"
    assert rows[2]["row_outcome"] == "invalid"
    assert rows[3]["binding_effect"] == "none"
    assert rows[3]["variant_resolution"] == "stay_current"
    assert rows[3]["row_outcome"] == "invalid"
    assert preview["summary"]["processed_count"] == 4
    assert preview["summary"]["bound_existing_variant_count"] == 1
    assert preview["summary"]["created_and_bound_variant_count"] == 1
    assert preview["summary"]["invalid_row_count"] == 1
    assert preview["summary"]["duplicate_key_count"] == 1
    assert preview["summary"]["created_entry_count"] == 1
    assert preview["summary"]["created_variant_count"] == 1
    assert preview["summary"]["binding_effect_counts"]["bind_count"] == 2
    assert preview["summary"]["variant_resolution_counts"]["reuse_existing_count"] == 1
    assert preview["summary"]["variant_resolution_counts"]["create_new_count"] == 1
    assert preview["summary"]["row_outcome_counts"]["applied_count"] == 2
    assert preview["summary"]["row_outcome_counts"]["invalid_count"] == 2
    assert branch_metadata_after == branch_metadata_before
    assert read_service.entries.get_entry("bootstrap.preview.new") is None


def test_branch_replace_only_rewrites_target_bindings() -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])
    read_service = branch_services()
    mutation_service = BranchMutationService()
    replace_service = BranchReplaceService()

    mutation_service.apply(
        BranchRef.dev(sample["dev_version"]),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
        },
    )
    mutation_service.apply(
        BranchRef.dev("2.4.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "series.other.branch",
                    "source": "Other branch source",
                    "translations_by_lang": {"fr": "Other branch text"},
                    "remarks_by_key": {"context": "other branch"},
                }
            ],
        },
    )

    source_before = read_service.list_branch_entries(BranchRef.dev(sample["dev_version"]))
    other_before = read_service.list_branch_entries(BranchRef.dev("2.4.1"))

    preview = replace_service.preview(BranchRef.dev(sample["dev_version"]), BranchRef.rel_current())
    result = replace_service.execute(BranchRef.dev(sample["dev_version"]), BranchRef.rel_current())

    rel_after = read_service.list_branch_entries(BranchRef.rel_current())
    source_after = read_service.list_branch_entries(BranchRef.dev(sample["dev_version"]))
    other_after = read_service.list_branch_entries(BranchRef.dev("2.4.1"))

    assert preview["request_echo"] == {
        "source_branch_ref": f"dev/{sample['dev_version']}",
        "target_branch_ref": "rel/current",
    }
    assert preview["summary"]["final_target_entry_count"] == len(source_before)
    assert "cleanup_binding_count" not in preview["summary"]
    assert "binding_effect_counts" not in preview["summary"]
    assert {row["business_key"] for row in rel_after} == {
        row["business_key"] for row in source_before
    }
    assert {
        row["business_key"]: row["variant_id"] for row in source_after
    } == {
        row["business_key"]: row["variant_id"] for row in source_before
    }
    assert other_after == other_before
    assert result["summary"]["final_target_entry_count"] == len(source_before)
    assert "cleanup_binding_count" not in result["summary"]
    assert "binding_effect_counts" not in result["summary"]


def test_effect_preview_summary_builder_counts_binding_variant_and_outcome() -> None:
    builder = EffectPreviewSummaryBuilder()
    rows = [
        {
            "binding_effect": "bind",
            "variant_resolution": "reuse_existing",
            "row_outcome": "applied",
        },
        {
            "binding_effect": "rebind",
            "variant_resolution": "reuse_existing",
            "row_outcome": "applied",
        },
        {
            "binding_effect": "none",
            "variant_resolution": "create_new",
            "row_outcome": "applied",
        },
        {
            "binding_effect": "none",
            "variant_resolution": "stay_current",
            "row_outcome": "noop",
        },
        {
            "binding_effect": "none",
            "variant_resolution": "stay_current",
            "row_outcome": "missing",
        },
    ]

    for row in rows:
        builder.add_row(row)

    assert builder.as_dict() == {
        "binding_effect_counts": {
            "none_count": 3,
            "bind_count": 1,
            "rebind_count": 1,
        },
        "variant_resolution_counts": {
            "stay_current_count": 2,
            "reuse_existing_count": 2,
            "create_new_count": 1,
        },
        "row_outcome_counts": {
            "applied_count": 3,
            "noop_count": 1,
            "missing_count": 1,
            "invalid_count": 0,
        },
    }


def test_branch_replace_preview_reports_rebind_target_when_variant_ids_differ() -> None:
    reset_demo()
    services = branch_services()
    BranchRegistryService().ensure_dev_branch("2.4.3", project_id=1)
    entry = services.entries.get_or_create_entry("replace.rebind", project_id=1)
    source_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "replace-source.xlsx",
            "Shared source",
            {"fr": "Source branch"},
            {"context": "source"},
        ),
    )
    target_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "replace-target.xlsx",
            "Different source",
            {"fr": "Target branch"},
            {"context": "target"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.3"), source_variant_id)
    services.bindings.bind(int(entry["entry_id"]), BranchRef.rel_current(), target_variant_id)

    preview = BranchReplaceService().preview(BranchRef.dev("2.4.3"), BranchRef.rel_current())
    row = next(item for item in preview["rows"] if item["business_key"] == "replace.rebind")
    execute = BranchReplaceService().execute(BranchRef.dev("2.4.3"), BranchRef.rel_current())
    execute_row = next(item for item in execute["report_rows"] if item["business_key"] == "replace.rebind")

    assert preview["preview_kind"] == "effect_forecast"
    assert preview["workflow_kind"] == "branch_replace"
    assert preview["request_echo"] == {
        "source_branch_ref": "dev/2.4.3",
        "target_branch_ref": "rel/current",
    }
    assert row["status"] == "REBIND_TARGET"
    assert row["binding_effect"] == "rebind"
    assert row["variant_resolution"] == "reuse_existing"
    assert row["row_outcome"] == "applied"
    assert execute_row["status"] == "REBIND_TARGET"
    assert execute_row["binding_effect"] == "rebind"
    assert execute_row["variant_resolution"] == "reuse_existing"
    assert execute_row["row_outcome"] == "applied"
    assert preview["summary"]["final_target_entry_count"] == 1
    assert preview["summary"]["added_to_target_count"] == 0
    assert preview["summary"]["kept_in_target_count"] == 0
    assert preview["summary"]["rebind_target_count"] == 1
    assert preview["summary"]["removed_from_target_count"] == 5
    assert "cleanup_binding_count" not in preview["summary"]
    assert "binding_effect_counts" not in preview["summary"]
    assert "variant_resolution_counts" not in preview["summary"]
    assert "row_outcome_counts" not in preview["summary"]
    assert "already_in_target_count" not in preview["summary"]
    assert execute["summary"]["final_target_entry_count"] == 1
    assert execute["summary"]["added_to_target_count"] == 0
    assert execute["summary"]["kept_in_target_count"] == 0
    assert execute["summary"]["rebind_target_count"] == 1
    assert execute["summary"]["removed_from_target_count"] == 5
    assert "cleanup_binding_count" not in execute["summary"]
    assert "binding_effect_counts" not in execute["summary"]
    assert "variant_resolution_counts" not in execute["summary"]
    assert "row_outcome_counts" not in execute["summary"]
    assert "already_in_target_count" not in execute["summary"]


def test_replace_rolls_back_when_target_rewrite_fails(monkeypatch) -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])
    read_service = branch_services()
    mutation_service = BranchMutationService()
    replace_service = BranchReplaceService()
    mutation_service.apply(
        BranchRef.dev(sample["dev_version"]),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
        },
    )

    rel_before = read_service.list_branch_entries(BranchRef.rel_current())
    dev_before = read_service.list_branch_entries(BranchRef.dev(sample["dev_version"]))

    def fail_upsert(*args, **kwargs):
        raise RuntimeError("replace rewrite failed")

    monkeypatch.setattr(replace_service.binding_commands, "upsert_binding", fail_upsert)

    with pytest.raises(RuntimeError, match="replace rewrite failed"):
        replace_service.execute(BranchRef.dev(sample["dev_version"]), BranchRef.rel_current())

    rel_after = read_service.list_branch_entries(BranchRef.rel_current())
    dev_after = read_service.list_branch_entries(BranchRef.dev(sample["dev_version"]))
    assert rel_after == rel_before
    assert dev_after == dev_before


def test_direct_mutation_rolls_back_on_failure(monkeypatch) -> None:
    reset_demo()
    mutation_service = BranchMutationService()
    read_service = branch_services()
    original_bind = mutation_service.bindings.bind
    call_count = {"value": 0}

    def fail_on_second_bind(*args, **kwargs):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise RuntimeError("direct mutation failed")
        return original_bind(*args, **kwargs)

    monkeypatch.setattr(mutation_service.bindings, "bind", fail_on_second_bind)

    with pytest.raises(RuntimeError, match="direct mutation failed"):
        mutation_service.apply(
            BranchRef.dev("2.4.3"),
            {
                "kind": "direct",
                "changes": [
                    {
                        "business_key": "tx.direct.one",
                        "source": "Direct source one",
                        "translations_by_lang": {"fr": "Direct target one"},
                        "remarks_by_key": {"context": "tx"},
                        "file_name": "tx-1.xlsx",
                    },
                    {
                        "business_key": "tx.direct.two",
                        "source": "Direct source two",
                        "translations_by_lang": {"fr": "Direct target two"},
                        "remarks_by_key": {"context": "tx"},
                        "file_name": "tx-2.xlsx",
                    },
                ],
            },
        )

    assert read_service.entries.get_entry("tx.direct.one") is None
    assert read_service.entries.get_entry("tx.direct.two") is None
    assert not any(branch["version"] == "2.4.3" for branch in read_service.list_dev_branches())


def test_import_batch_mutation_rolls_back_on_failure(monkeypatch) -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])
    mutation_service = BranchMutationService()
    read_service = branch_services()
    original_bind = mutation_service.bindings.bind
    call_count = {"value": 0}

    def fail_on_second_bind(*args, **kwargs):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise RuntimeError("import batch failed")
        return original_bind(*args, **kwargs)

    monkeypatch.setattr(mutation_service.bindings, "bind", fail_on_second_bind)

    with pytest.raises(RuntimeError, match="import batch failed"):
        mutation_service.apply(
            BranchRef.dev(sample["dev_version"]),
            {
                "kind": "import_batch",
                "import_batch_id": batch["import_batch_id"],
            },
        )

    assert read_service.entries.get_entry("dev.new.entry") is None
    assert not any(
        branch["version"] == sample["dev_version"] for branch in read_service.list_dev_branches()
    )


def test_direct_content_update_emits_phase4_semantics() -> None:
    reset_demo()
    services = branch_services()
    mutation_service = BranchMutationService()

    entry = services.entries.get_or_create_entry("phase4.content.update", project_id=1)
    variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "phase4-content.xlsx",
            "Phase 4 content source",
            {"fr": "Original phase 4 text"},
            {"context": "original phase 4"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.rel_current(), variant_id)

    result = mutation_service.apply(
        BranchRef.rel_current(),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "phase4.content.update",
                    "translations_by_lang": {"fr": "Updated phase 4 text"},
                }
            ],
        },
    )

    updated_entry = next(
        item for item in services.list_branch_entries(BranchRef.rel_current()) if item["business_key"] == "phase4.content.update"
    )
    updated_variant = services.catalog.get_variant(variant_id)
    assert updated_entry["variant_id"] == variant_id
    assert updated_variant["translations"]["fr"] == "Updated phase 4 text"
    assert updated_variant["remarks"]["context"] == "original phase 4"

    row = result["report_rows"][0]
    assert row["status"] == "UPDATED_BOUND_VARIANT"
    assert row["mutation_class"] == "content"
    assert row["binding_effect"] == "none"
    assert row["variant_resolution"] == "stay_current"
    assert row["content_effect"] == "update"
    assert row["row_outcome"] == "applied"
    assert result["summary"]["updated_bound_variant_count"] == 1
    assert result["summary"]["mutation_class_counts"]["range_count"] == 0
    assert result["summary"]["mutation_class_counts"]["content_count"] == 1
    assert result["summary"]["binding_effect_counts"]["none_count"] == 1
    assert result["summary"]["binding_effect_counts"]["bind_count"] == 0
    assert result["summary"]["binding_effect_counts"]["rebind_count"] == 0
    assert result["summary"]["variant_resolution_counts"]["stay_current_count"] == 1
    assert result["summary"]["variant_resolution_counts"]["reuse_existing_count"] == 0
    assert result["summary"]["variant_resolution_counts"]["create_new_count"] == 0
    assert result["summary"]["content_effect_counts"]["none_count"] == 0
    assert result["summary"]["content_effect_counts"]["create_count"] == 0
    assert result["summary"]["content_effect_counts"]["update_count"] == 1
    assert result["summary"]["content_effect_counts"]["filtered_count"] == 0
    assert result["summary"]["row_outcome_counts"]["applied_count"] == 1
    assert result["summary"]["row_outcome_counts"]["noop_count"] == 0
    assert result["summary"]["row_outcome_counts"]["missing_count"] == 0


def test_direct_content_mutation_missing_target_emits_missing_semantics() -> None:
    reset_demo()
    services = branch_services()
    mutation_service = BranchMutationService()

    result = mutation_service.apply(
        BranchRef.rel_current(),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "phase4.direct.missing.target",
                    "translations_by_lang": {"fr": "Bonjour missing"},
                }
            ],
        },
    )

    assert services.entries.get_entry("phase4.direct.missing.target") is None
    assert not any(
        item["business_key"] == "phase4.direct.missing.target"
        for item in services.list_branch_entries(BranchRef.rel_current())
    )

    row = result["report_rows"][0]
    assert row["status"] == "MISSING_IN_SCOPE"
    assert row["mutation_class"] == "content"
    assert row["binding_effect"] == "none"
    assert row["variant_resolution"] == "stay_current"
    assert row["content_effect"] == "none"
    assert row["row_outcome"] == "missing"
    assert result["summary"]["variant_resolution_counts"]["stay_current_count"] == 1
    assert result["summary"]["row_outcome_counts"]["missing_count"] == 1


def test_direct_range_create_emits_bind_and_create_semantics() -> None:
    reset_demo()
    services = branch_services()
    mutation_service = BranchMutationService()

    result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "phase4.direct.create",
                    "source": "Phase 4 source",
                    "translations_by_lang": {"fr": "Bonjour phase 4"},
                    "remarks_by_key": {"context": "phase4"},
                    "file_name": "phase4.xlsx",
                }
            ],
        },
    )

    created_entry = services.entries.get_entry("phase4.direct.create")
    assert created_entry is not None
    created_dev_entry = next(
        item for item in services.list_branch_entries(BranchRef.dev("2.4.3")) if item["business_key"] == "phase4.direct.create"
    )
    created_variant = services.catalog.get_variant(created_dev_entry["variant_id"])
    assert created_dev_entry["variant_id"] is not None
    assert created_variant["file_name"] == "phase4.xlsx"
    assert created_variant["translations"]["fr"] == "Bonjour phase 4"
    assert created_variant["remarks"]["context"] == "phase4"

    row = result["report_rows"][0]
    assert row["status"] == "CREATED_AND_BOUND_VARIANT"
    assert row["mutation_class"] == "range"
    assert row["binding_effect"] == "bind"
    assert row["variant_resolution"] == "create_new"
    assert row["content_effect"] == "create"
    assert row["row_outcome"] == "applied"
    assert result["summary"]["variant_resolution_counts"]["create_new_count"] == 1


def test_direct_filtered_rebind_emits_range_rebind_filtered_semantics() -> None:
    reset_demo()
    services = branch_services()
    mutation_service = BranchMutationService()

    entry = services.entries.get_or_create_entry("authority.rebind.filtered", project_id=1)
    current_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "authority-current.xlsx",
            "Current source",
            {"fr": "Current text"},
            {"context": "current"},
        ),
    )
    target_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "authority-target.xlsx",
            "Target source",
            {"fr": "Target text"},
            {"context": "target"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.5.1"), current_variant_id)
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.2"), target_variant_id)

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "authority.rebind.filtered",
                    "source": "Target source",
                    "translations_by_lang": {"fr": "Filtered target text"},
                    "remarks_by_key": {"context": "Filtered target remark"},
                }
            ],
        },
    )

    target_entry = next(item for item in services.list_branch_entries(BranchRef.dev("2.5.1")) if item["business_key"] == "authority.rebind.filtered")
    target_variant = services.catalog.get_variant(target_variant_id)
    assert target_entry["variant_id"] == target_variant_id
    assert target_variant["translations"]["fr"] == "Target text"
    assert target_variant["remarks"]["context"] == "target"

    row = result["report_rows"][0]
    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert row["content_filtered_by_authority"] is True
    assert row["mutation_class"] == "range"
    assert row["binding_effect"] == "rebind"
    assert row["variant_resolution"] == "reuse_existing"
    assert row["content_effect"] == "filtered"
    assert row["row_outcome"] == "applied"
    assert result["summary"]["content_effect_counts"]["filtered_count"] == 1
    assert result["summary"]["binding_effect_counts"]["rebind_count"] == 1
    assert result["summary"]["variant_resolution_counts"]["reuse_existing_count"] == 1


def test_direct_mutation_preview_is_read_only_and_reports_effect_forecast() -> None:
    reset_demo()
    services = branch_services()
    mutation_service = BranchMutationService()

    content_entry = services.entries.get_or_create_entry("preview.direct.content", project_id=1)
    content_variant_id = services.catalog.create_variant(
        int(content_entry["entry_id"]),
        services.catalog.build_content(
            "preview-direct.xlsx",
            "Preview direct source",
            {"fr": "Original preview text"},
            {"context": "preview"},
        ),
    )
    services.bindings.bind(int(content_entry["entry_id"]), BranchRef.dev("2.5.1"), content_variant_id)

    rebind_entry = services.entries.get_or_create_entry("preview.direct.rebind", project_id=1)
    rebind_current_variant_id = services.catalog.create_variant(
        int(rebind_entry["entry_id"]),
        services.catalog.build_content(
            "preview-rebind-current.xlsx",
            "Preview rebind current source",
            {"fr": "Current rebind text"},
            {"context": "current"},
        ),
    )
    rebind_target_variant_id = services.catalog.create_variant(
        int(rebind_entry["entry_id"]),
        services.catalog.build_content(
            "preview-rebind-target.xlsx",
            "Preview rebind target source",
            {"fr": "Target rebind text"},
            {"context": "target"},
        ),
    )
    services.bindings.bind(int(rebind_entry["entry_id"]), BranchRef.dev("2.5.1"), rebind_current_variant_id)

    services.entries.get_or_create_entry("preview.direct.create", project_id=1)

    preview = mutation_service.preview(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "preview.direct.content",
                    "translations_by_lang": {"fr": "Preview-only text"},
                }
                ,
                {
                    "business_key": "preview.direct.rebind",
                    "source": "Preview rebind target source",
                },
                {
                    "business_key": "preview.direct.create",
                    "source": "Preview create source",
                    "translations_by_lang": {"fr": "Created preview text"},
                    "remarks_by_key": {"context": "create"},
                    "file_name": "preview-create.xlsx",
                },
                {
                    "business_key": "preview.direct.missing",
                    "translations_by_lang": {"fr": "Missing preview text"},
                },
                {
                    "translations_by_lang": {"fr": "Invalid preview text"},
                },
            ],
        },
    )

    rows = {row["business_key"]: row for row in preview["rows"] if row.get("business_key")}
    invalid_row = next(row for row in preview["rows"] if row["row_outcome"] == "invalid")
    content_variant = services.catalog.get_variant(content_variant_id)
    rebind_target_variant = services.catalog.get_variant(rebind_target_variant_id)

    assert preview["preview_kind"] == "effect_forecast"
    assert preview["workflow_kind"] == "branch_mutation"
    assert preview["request_echo"]["branch_ref"] == "dev/2.5.1"
    assert preview["request_echo"]["input_kind"] == "direct"
    assert rows["preview.direct.content"]["status"] == "UPDATED_BOUND_VARIANT"
    assert rows["preview.direct.content"]["binding_effect"] == "none"
    assert rows["preview.direct.content"]["variant_resolution"] == "stay_current"
    assert rows["preview.direct.content"]["row_outcome"] == "applied"
    assert rows["preview.direct.rebind"]["status"] == "BOUND_EXISTING_VARIANT"
    assert rows["preview.direct.rebind"]["binding_effect"] == "rebind"
    assert rows["preview.direct.rebind"]["variant_resolution"] == "reuse_existing"
    assert rows["preview.direct.rebind"]["row_outcome"] == "applied"
    assert rows["preview.direct.create"]["status"] == "CREATED_AND_BOUND_VARIANT"
    assert rows["preview.direct.create"]["binding_effect"] == "bind"
    assert rows["preview.direct.create"]["variant_resolution"] == "create_new"
    assert rows["preview.direct.create"]["row_outcome"] == "applied"
    assert rows["preview.direct.missing"]["status"] == "MISSING_IN_SCOPE"
    assert rows["preview.direct.missing"]["binding_effect"] == "none"
    assert rows["preview.direct.missing"]["variant_resolution"] == "stay_current"
    assert rows["preview.direct.missing"]["row_outcome"] == "missing"
    assert invalid_row["status"] == "INVALID_ROW"
    assert invalid_row["binding_effect"] == "none"
    assert invalid_row["variant_resolution"] == "stay_current"
    assert invalid_row["row_outcome"] == "invalid"
    assert preview["summary"]["binding_effect_counts"]["none_count"] == 3
    assert preview["summary"]["binding_effect_counts"]["bind_count"] == 1
    assert preview["summary"]["binding_effect_counts"]["rebind_count"] == 1
    assert preview["summary"]["variant_resolution_counts"]["stay_current_count"] == 3
    assert preview["summary"]["variant_resolution_counts"]["reuse_existing_count"] == 1
    assert preview["summary"]["variant_resolution_counts"]["create_new_count"] == 1
    assert preview["summary"]["row_outcome_counts"]["applied_count"] == 3
    assert preview["summary"]["row_outcome_counts"]["missing_count"] == 1
    assert preview["summary"]["row_outcome_counts"]["invalid_count"] == 1
    assert content_variant["translations"]["fr"] == "Original preview text"
    assert rebind_target_variant["translations"]["fr"] == "Target rebind text"


def test_import_batch_content_update_emits_phase4_semantics(tmp_path) -> None:
    reset_demo()
    mutation_service = BranchMutationService()
    services = branch_services()

    entry = services.entries.get_or_create_entry("import.batch.content.update", project_id=1)
    variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "content-update.xlsx",
            "Content source",
            {"fr": "Original content"},
            {"context": "original"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.3"), variant_id)

    import_root = tmp_path / "content-update-import"
    write_import_workbook(
        import_root,
        "bundle/content-update.xlsx",
        [
            ["business_key", "source", "fr", "context"],
            ["import.batch.content.update", "Content source", "Updated content", "Updated context"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "UPDATED_BOUND_VARIANT"
    assert row["mutation_class"] == "content"
    assert row["binding_effect"] == "none"
    assert row["variant_resolution"] == "stay_current"
    assert row["content_effect"] == "update"
    assert row["row_outcome"] == "applied"
    assert result["summary"]["mutation_class_counts"]["content_count"] == 1
    assert result["summary"]["binding_effect_counts"]["none_count"] == 1
    assert result["summary"]["variant_resolution_counts"]["stay_current_count"] == 1
    assert result["summary"]["content_effect_counts"]["update_count"] == 1
    assert result["summary"]["row_outcome_counts"]["applied_count"] == 1


def test_import_batch_filtered_rebind_emits_phase4_semantics(tmp_path) -> None:
    reset_demo()
    mutation_service = BranchMutationService()
    services = branch_services()

    entry = services.entries.get_or_create_entry("import.batch.filtered.rebind", project_id=1)
    current_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "current.xlsx",
            "Current source",
            {"fr": "Current content"},
            {"context": "current"},
        ),
    )
    target_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "target.xlsx",
            "Target source",
            {"fr": "Target content"},
            {"context": "target"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.5.1"), current_variant_id)
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.2"), target_variant_id)

    import_root = tmp_path / "filtered-rebind-import"
    write_import_workbook(
        import_root,
        "bundle/filtered-rebind.xlsx",
        [
            ["business_key", "source", "fr", "context"],
            ["import.batch.filtered.rebind", "Target source", "Filtered content", "Filtered context"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert row["content_filtered_by_authority"] is True
    assert row["mutation_class"] == "range"
    assert row["binding_effect"] == "rebind"
    assert row["variant_resolution"] == "reuse_existing"
    assert row["content_effect"] == "filtered"
    assert row["row_outcome"] == "applied"
    assert result["summary"]["mutation_class_counts"]["range_count"] == 1
    assert result["summary"]["binding_effect_counts"]["rebind_count"] == 1
    assert result["summary"]["variant_resolution_counts"]["reuse_existing_count"] == 1
    assert result["summary"]["content_effect_counts"]["filtered_count"] == 1
    assert result["summary"]["row_outcome_counts"]["applied_count"] == 1


def test_import_batch_sparse_patch_preserves_unmapped_languages_and_remarks(tmp_path) -> None:
    reset_demo()
    mutation_service = BranchMutationService()
    read_service = branch_services()

    create_result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "single.lang.patch",
                    "source": "Single source",
                    "translations_by_lang": {
                        "fr": "Bonjour initial",
                        "en": "Hello initial",
                    },
                    "remarks_by_key": {"context": "Initial context"},
                    "file_name": "single.xlsx",
                }
            ],
        },
    )
    assert create_result["report_rows"][0]["status"] == "CREATED_AND_BOUND_VARIANT"

    import_root = tmp_path / "single-lang-import"
    write_import_workbook(
        import_root,
        "bundle/single.xlsx",
        [
            ["business_key", "source", "fr"],
            ["single.lang.patch", "Single source", "Bonjour patch"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
        },
    )
    assert result["report_rows"][0]["status"] == "UPDATED_BOUND_VARIANT"

    dev_entries = read_service.list_branch_entries(BranchRef.dev("2.4.3"))
    entry = next(item for item in dev_entries if item["business_key"] == "single.lang.patch")
    assert entry["translations"]["fr"] == "Bonjour patch"
    assert entry["translations"]["en"] == "Hello initial"
    assert entry["remarks"]["context"] == "Initial context"


def test_import_batch_source_switch_preserves_existing_target_variant_fields(tmp_path) -> None:
    reset_demo()
    mutation_service = BranchMutationService()
    inspection = EntryTimelineDataset()

    current_result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "source.switch.existing",
                    "source": "Current source",
                    "translations_by_lang": {
                        "fr": "Bonjour current",
                        "en": "Hello current",
                    },
                    "remarks_by_key": {"context": "Current context"},
                    "file_name": "current.xlsx",
                }
            ],
        },
    )
    assert current_result["report_rows"][0]["status"] == "CREATED_AND_BOUND_VARIANT"

    target_result = mutation_service.apply(
        BranchRef.dev("2.4.2"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "source.switch.existing",
                    "source": "Target source",
                    "translations_by_lang": {
                        "fr": "Bonjour target",
                        "en": "Hello target",
                    },
                    "remarks_by_key": {"context": "Target context"},
                    "file_name": "target.xlsx",
                }
            ],
        },
    )
    assert target_result["report_rows"][0]["status"] == "CREATED_AND_BOUND_VARIANT"

    import_root = tmp_path / "source-switch-existing"
    write_import_workbook(
        import_root,
        "bundle/source-switch.xlsx",
        [
            ["business_key", "source", "fr"],
            ["source.switch.existing", "Target source", "Bonjour import"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
        },
    )
    assert result["report_rows"][0]["status"] == "UPDATED_AND_BOUND_EXISTING_VARIANT"

    variants = inspection.get("source.switch.existing")["variants"]
    target_variant = next(item for item in variants if item["source"] == "Target source")

    assert target_variant["translations"]["fr"] == "Bonjour import"
    assert target_variant["translations"]["en"] == "Hello target"
    assert target_variant["remarks"]["context"] == "Target context"
    assert any(binding["branch_ref"] == "dev/2.4.3" for binding in target_variant["bindings"])


def test_import_batch_source_switch_new_variant_does_not_inherit_current_fields(tmp_path) -> None:
    reset_demo()
    mutation_service = BranchMutationService()
    inspection = EntryTimelineDataset()

    current_result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "source.switch.new",
                    "source": "Current source",
                    "translations_by_lang": {
                        "fr": "Bonjour current",
                        "en": "Hello current",
                    },
                    "remarks_by_key": {"context": "Current context"},
                    "file_name": "current.xlsx",
                }
            ],
        },
    )
    assert current_result["report_rows"][0]["status"] == "CREATED_AND_BOUND_VARIANT"

    import_root = tmp_path / "source-switch-new"
    write_import_workbook(
        import_root,
        "bundle/source-switch.xlsx",
        [
            ["business_key", "source", "fr"],
            ["source.switch.new", "Brand new source", "Bonjour import"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
        },
    )
    assert result["report_rows"][0]["status"] == "CREATED_AND_BOUND_VARIANT"

    variants = inspection.get("source.switch.new")["variants"]
    new_variant = next(item for item in variants if item["source"] == "Brand new source")

    assert new_variant["translations"] == {"fr": "Bonjour import"}
    assert new_variant["remarks"] == {}
    assert any(binding["branch_ref"] == "dev/2.4.3" for binding in new_variant["bindings"])


def test_release_branch_rejects_import_batch_mutation() -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    with pytest.raises(ValueError, match="rel/current only supports direct mutations"):
        BranchMutationService().apply(
            BranchRef.rel_current(),
            {
                "kind": "import_batch",
                "import_batch_id": batch["import_batch_id"],
            },
        )


def test_release_hotfix_and_branch_delete_produces_orphan() -> None:
    sample = reset_demo()
    mutation_service = BranchMutationService()
    variant_service = TrashRestoreService()

    active = mutation_service.apply(
        BranchRef.rel_current(),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": sample["active_hotfix"]["business_key"],
                    "translations_by_lang": {
                        sample["active_hotfix"]["lang"]: sample["active_hotfix"]["target_text"],
                    },
                }
            ],
        },
    )
    assert active["summary"]["updated_bound_variant_count"] == 1

    passive = mutation_service.apply(
        BranchRef.rel_current(),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": sample["passive_hotfix"]["business_key"],
                    "source": sample["passive_hotfix"]["source"],
                    "translations_by_lang": sample["passive_hotfix"]["translations_by_lang"],
                    "remarks_by_key": sample["passive_hotfix"]["remarks_by_key"],
                    "file_name": sample["passive_hotfix"]["file_name"],
                }
            ],
        },
    )
    assert passive["report_rows"][0]["status"] in {"CREATED_AND_BOUND_VARIANT", "UPDATED_AND_BOUND_EXISTING_VARIANT"}

    before_delete = EntryTimelineDataset().get("common.welcome")
    target_variant_id = before_delete["variants"][0]["variant_id"]
    delete_result = variant_service.delete(BranchRef.rel_current(), ["common.welcome"])
    assert delete_result["summary"]["orphaned_variant_count"] == 1

    after_delete = EntryTimelineDataset().get("common.welcome")
    orphaned = next(v for v in after_delete["variants"] if v["variant_id"] == target_variant_id)
    assert orphaned["is_orphaned"] is True
    assert orphaned["is_trashed"] is False


def test_branch_delete_produces_orphan_instead_of_trashed() -> None:
    sample = reset_demo()
    variant_service = TrashRestoreService()
    inspection = EntryTimelineDataset()

    before = inspection.get("common.welcome")
    target_variant_id = before["variants"][0]["variant_id"]
    assert before["variants"][0]["is_trashed"] is False

    result = variant_service.delete(BranchRef.rel_current(), ["common.welcome"])

    assert result["summary"]["orphaned_variant_count"] == 1
    assert "trashed_variant_count" not in result["summary"]
    orphan_row = next(r for r in result["report_rows"] if r["business_key"] == "common.welcome")
    assert orphan_row["status"] == "ORPHANED_VARIANT"

    after = inspection.get("common.welcome")
    variant_after = next(v for v in after["variants"] if v["variant_id"] == target_variant_id)
    assert variant_after["is_orphaned"] is True
    assert variant_after["is_trashed"] is False
    assert variant_after["trashed_at"] is None


def test_delete_rolls_back_on_failure(monkeypatch) -> None:
    reset_demo()
    variant_service = TrashRestoreService()
    read_service = branch_services()

    def fail_refresh(*args, **kwargs):
        raise RuntimeError("delete refresh failed")

    monkeypatch.setattr(variant_service.lifecycle, "refresh_orphan_states", fail_refresh)

    with pytest.raises(RuntimeError, match="delete refresh failed"):
        variant_service.delete(BranchRef.rel_current(), ["common.welcome"])

    rel_keys = {item["business_key"] for item in read_service.list_branch_entries(BranchRef.rel_current())}
    assert "common.welcome" in rel_keys


def test_direct_dev_mutation_reuses_rel_owned_variant_and_creates_missing_entries() -> None:
    reset_demo()
    mutation_service = BranchMutationService()
    read_service = branch_services()

    result = mutation_service.apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "rel.locked.same",
                    "source": "Release same source",
                    "translations_by_lang": {"fr": "Should stay rel-owned"},
                },
                {
                    "business_key": "dev.direct.new",
                    "source": "New direct source",
                    "translations_by_lang": {"fr": "Nouvelle entree"},
                    "remarks_by_key": {"context": "direct"},
                    "file_name": "direct.xlsx",
                },
            ],
        },
    )
    statuses = {row["business_key"]: row["status"] for row in result["report_rows"]}
    assert statuses["rel.locked.same"] == "BOUND_EXISTING_VARIANT"
    assert statuses["dev.direct.new"] == "CREATED_AND_BOUND_VARIANT"

    dev_entries = read_service.list_branch_entries(BranchRef.dev("2.4.3"))
    assert any(item["business_key"] == "dev.direct.new" for item in dev_entries)


def test_lower_authority_shared_current_same_variant_edit_is_filtered_but_binding_is_kept() -> None:
    reset_demo()
    services = branch_services()
    mutation_service = BranchMutationService()

    entry = services.entries.get_or_create_entry("authority.shared.current", project_id=1)
    variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "authority.xlsx",
            "Shared source",
            {"fr": "Authoritative text"},
            {"context": "authoritative"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.2"), variant_id)
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.5.1"), variant_id)

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "authority.shared.current",
                    "source": "Shared source",
                    "translations_by_lang": {"fr": "Filtered text"},
                    "remarks_by_key": {"context": "Filtered remark"},
                }
            ],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "NOOP"
    assert row["content_filtered_by_authority"] is True
    assert result["summary"]["content_filtered_by_authority_count"] == 1
    current_variant = services.catalog.get_variant(variant_id)
    assert current_variant["translations"]["fr"] == "Authoritative text"
    assert current_variant["remarks"]["context"] == "authoritative"


def test_lower_authority_rebind_filtered_source_switch_rebinds_existing_target_and_filters_content() -> None:
    reset_demo()
    services = branch_services()
    mutation_service = BranchMutationService()

    entry = services.entries.get_or_create_entry("authority.rebind.filtered", project_id=1)
    current_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "authority-current.xlsx",
            "Current source",
            {"fr": "Current text"},
            {"context": "current"},
        ),
    )
    target_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "authority-target.xlsx",
            "Target source",
            {"fr": "Target text"},
            {"context": "target"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.5.1"), current_variant_id)
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.2"), target_variant_id)

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "authority.rebind.filtered",
                    "source": "Target source",
                    "translations_by_lang": {"fr": "Filtered target text"},
                    "remarks_by_key": {"context": "Filtered target remark"},
                }
            ],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert row["content_filtered_by_authority"] is True

    dev_entries = services.list_branch_entries(BranchRef.dev("2.5.1"))
    dev_entry = next(item for item in dev_entries if item["business_key"] == "authority.rebind.filtered")
    assert dev_entry["variant_id"] == target_variant_id
    target_variant = services.catalog.get_variant(target_variant_id)
    assert target_variant["translations"]["fr"] == "Target text"
    assert target_variant["remarks"]["context"] == "target"


def test_lower_authority_orphan_variant_can_be_rebound_and_edited_in_one_row() -> None:
    reset_demo()
    services = branch_services()
    mutation_service = BranchMutationService()

    entry = services.entries.get_or_create_entry("authority.orphan.rebind", project_id=1)
    orphan_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "authority-orphan.xlsx",
            "Orphan source",
            {"fr": "Orphan text"},
            {"context": "orphan"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.2"), orphan_variant_id)
    services.bindings.remove_bindings([BranchRef.dev("2.4.2")])

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "authority.orphan.rebind",
                    "source": "Orphan source",
                    "translations_by_lang": {"fr": "Edited orphan text"},
                    "remarks_by_key": {"context": "Edited orphan remark"},
                }
            ],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "UPDATED_AND_BOUND_EXISTING_VARIANT"
    assert not row.get("content_filtered_by_authority")

    dev_entries = services.list_branch_entries(BranchRef.dev("2.5.1"))
    dev_entry = next(item for item in dev_entries if item["business_key"] == "authority.orphan.rebind")
    assert dev_entry["variant_id"] == orphan_variant_id
    orphan_variant = services.catalog.get_variant(orphan_variant_id)
    assert orphan_variant["translations"]["fr"] == "Edited orphan text"
    assert orphan_variant["remarks"]["context"] == "Edited orphan remark"


def test_branch_authority_prefers_higher_series_and_later_patch() -> None:
    assert AuthorityPolicy.key_for_branch(BranchRef.rel_current()) > AuthorityPolicy.key_for_branch(BranchRef.dev("2.4.3"))
    assert AuthorityPolicy.key_for_branch(BranchRef.dev("2.4.3")) > AuthorityPolicy.key_for_branch(BranchRef.dev("2.4.2"))
    assert AuthorityPolicy.key_for_branch(BranchRef.dev("2.4.1")) > AuthorityPolicy.key_for_branch(BranchRef.dev("2.5.3"))


def test_lower_authority_dev_cannot_override_higher_authority_dev_variant() -> None:
    reset_demo()
    service = branch_services()
    entries = service.entries
    bindings = service.bindings
    catalog = service.catalog
    mutation_service = BranchMutationService()

    entry = entries.get_or_create_entry("authority.series", project_id=1)
    variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        catalog.build_content(
            "authority.xlsx",
            "Shared source",
            {"fr": "Series owner"},
            {"context": "authority"},
        ),
    )
    bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.2"), variant_id)

    rebind_result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "authority.series",
                    "source": "Shared source",
                    "translations_by_lang": {"fr": "Series owner"},
                }
            ],
        },
    )

    assert rebind_result["report_rows"][0]["status"] == "BOUND_EXISTING_VARIANT"
    assert rebind_result["summary"]["bound_existing_variant_count"] == 1

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "authority.series",
                    "source": "Shared source",
                    "translations_by_lang": {"fr": "Should not win"},
                }
            ],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "NOOP"
    assert row["content_filtered_by_authority"] is True
    assert result["summary"]["content_filtered_by_authority_count"] == 1
    assert catalog.get_variant(variant_id)["translations"]["fr"] == "Series owner"


def test_lower_authority_dev_cannot_change_existing_higher_authority_variant_in_import_batch(tmp_path) -> None:
    reset_demo()
    service = branch_services()
    entry = service.entries.get_or_create_entry("authority.import", project_id=1)
    variant_id = service.catalog.create_variant(
        int(entry["entry_id"]),
        service.catalog.build_content(
            "authority.xlsx",
            "Shared source",
            {"fr": "Import owner"},
            {"context": "authority"},
        ),
    )
    service.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.2"), variant_id)

    import_root = tmp_path / "authority-import"
    write_import_workbook(
        import_root,
        "bundle/authority.xlsx",
        [
            ["business_key", "source", "fr"],
            ["authority.import", "Shared source", "Should not win"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = BranchMutationService().apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert row["content_filtered_by_authority"] is True
    assert result["summary"]["content_filtered_by_authority_count"] == 1
    assert service.catalog.get_variant(variant_id)["translations"]["fr"] == "Import owner"


def test_lower_authority_import_batch_rebinds_existing_target_and_filtered_content(tmp_path) -> None:
    reset_demo()
    services = branch_services()
    mutation_service = BranchMutationService()
    inspection = EntryTimelineDataset()

    entry = services.entries.get_or_create_entry("authority.import.filtered", project_id=1)
    actor_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "actor.xlsx",
            "Actor source",
            {"fr": "Actor content"},
            {"context": "actor"},
        ),
    )
    target_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "target.xlsx",
            "Target source",
            {"fr": "Target owner"},
            {"context": "target"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.5.1"), actor_variant_id)
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.2"), target_variant_id)

    import_root = tmp_path / "authority-import-filtered"
    write_import_workbook(
        import_root,
        "bundle/authority.xlsx",
        [
            ["business_key", "source", "fr", "context"],
            ["authority.import.filtered", "Target source", "Filtered import", "filtered"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))

    result = mutation_service.apply(
        BranchRef.dev("2.5.1"),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
        },
    )

    row = result["report_rows"][0]
    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert row["content_filtered_by_authority"] is True
    assert result["summary"]["content_filtered_by_authority_count"] == 1

    dev_entry = next(item for item in inspection.get("authority.import.filtered")["variants"] if item["variant_id"] == target_variant_id)
    assert any(binding["branch_ref"] == "dev/2.5.1" for binding in dev_entry["bindings"])
    assert services.catalog.get_variant(target_variant_id)["translations"]["fr"] == "Target owner"
    assert services.catalog.get_variant(target_variant_id)["remarks"]["context"] == "target"


def test_higher_authority_dev_can_override_lower_authority_dev_variant() -> None:
    reset_demo()
    service = branch_services()
    entry = service.entries.get_or_create_entry("authority.patch", project_id=1)
    variant_id = service.catalog.create_variant(
        int(entry["entry_id"]),
        service.catalog.build_content(
            "authority.xlsx",
            "Shared source",
            {"fr": "Patch owner"},
            {"context": "authority"},
        ),
    )
    service.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.2"), variant_id)

    result = BranchMutationService().apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "authority.patch",
                    "source": "Shared source",
                    "translations_by_lang": {"fr": "Patch winner"},
                }
            ],
        },
    )

    assert result["report_rows"][0]["status"] == "UPDATED_AND_BOUND_EXISTING_VARIANT"
    assert service.catalog.get_variant(variant_id)["translations"]["fr"] == "Patch winner"


def test_bootstrap_preview_rejects_nonexistent_dev_branch(tmp_path) -> None:
    reset_demo()
    import_root = tmp_path / "bootstrap-missing-branch"
    write_import_workbook(
        import_root,
        "bundle/missing.xlsx",
        [
            ["business_key", "source", "fr"],
            ["some.key", "Some source", "Some text"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))
    with pytest.raises(KeyError, match="dev branch not found"):
        BranchBootstrapService().preview(BranchRef.dev("2.4.99"), batch["import_batch_id"])


def test_bootstrap_preview_reuse_hit_always_reports_bind(tmp_path) -> None:
    sample = reset_demo()
    services = branch_services()
    BranchRegistryService().ensure_dev_branch(sample["dev_version"], project_id=1)
    existing = next(
        item
        for item in services.list_branch_entries(BranchRef.rel_current())
        if item["business_key"] == "rel.locked.same"
    )
    services.bindings.bind(
        int(existing["entry_id"]),
        BranchRef.dev(sample["dev_version"]),
        int(existing["variant_id"]),
    )
    import_root = tmp_path / "bootstrap-reuse-bind"
    write_import_workbook(
        import_root,
        "bundle/reuse-bind.xlsx",
        [
            ["business_key", "source", "fr"],
            [existing["business_key"], existing["source"], "Reuse text"],
        ],
    )
    batch = ImportService().import_directory(str(import_root))
    preview = BranchBootstrapService().preview(
        BranchRef.dev(sample["dev_version"]), batch["import_batch_id"]
    )
    row = preview["rows"][0]
    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert row["binding_effect"] == "rebind"
    assert row["variant_resolution"] == "reuse_existing"
    assert row["row_outcome"] == "applied"
    assert preview["summary"]["binding_effect_counts"]["rebind_count"] == 1
    assert preview["summary"]["binding_effect_counts"]["none_count"] == 0


def test_mutation_preview_blank_source_returns_invalid_row() -> None:
    reset_demo()
    services = branch_services()
    entry = services.entries.get_or_create_entry("preview.blank.source", project_id=1)
    variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "blank-source.xlsx",
            "Original source",
            {"fr": "Original text"},
            {"context": "original"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.5.1"), variant_id)

    preview = BranchMutationService().preview(
        BranchRef.dev("2.5.1"),
        {
            "kind": "direct",
            "changes": [
                {
                    "business_key": "preview.blank.source",
                    "source": "   ",
                    "translations_by_lang": {"fr": "New text"},
                },
                {
                    "business_key": "preview.blank.source",
                    "source": "",
                    "translations_by_lang": {"fr": "New text"},
                },
            ],
        },
    )

    assert len(preview["rows"]) == 2
    for row in preview["rows"]:
        assert row["status"] == "INVALID_ROW"
        assert row["row_outcome"] == "invalid"
        assert row["binding_effect"] == "none"
        assert row["variant_resolution"] == "stay_current"
    assert preview["summary"]["row_outcome_counts"]["invalid_count"] == 2


def test_project_trash_trashes_orphan_variants_only() -> None:
    reset_demo()
    read_service = branch_services()
    variant_service = TrashRestoreService()

    variant_service.delete(BranchRef.rel_current(), ["common.welcome"])

    result = variant_service.project_trash(["common.welcome"])

    assert result["summary"]["trashed_count"] == 1
    assert result["summary"]["not_orphan_count"] == 0
    assert result["summary"]["no_orphan_found_count"] == 0
    assert result["summary"]["missing_count"] == 0

    trashed_row = next(r for r in result["report_rows"] if r["business_key"] == "common.welcome")
    assert trashed_row["status"] == "TRASHED"

    after = EntryTimelineDataset().get("common.welcome")
    variant = next(v for v in after["variants"] if v["variant_id"] == trashed_row["variant_id"])
    assert variant["is_trashed"] is True


def test_project_trash_rejects_active_variants() -> None:
    reset_demo()
    variant_service = TrashRestoreService()

    result = variant_service.project_trash(["common.welcome"])

    assert result["summary"]["not_orphan_count"] == 1
    assert result["summary"]["trashed_count"] == 0
    active_row = next(r for r in result["report_rows"] if r["business_key"] == "common.welcome")
    assert active_row["status"] == "NOT_ORPHAN"


def test_project_trash_reports_missing_keys() -> None:
    reset_demo()
    variant_service = TrashRestoreService()

    result = variant_service.project_trash(["nonexistent.key"])

    assert result["summary"]["missing_count"] == 1
    assert result["report_rows"][0]["status"] == "MISSING"
