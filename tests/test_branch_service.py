from pathlib import Path

import pytest

from app.db import get_db_path
from app.services.branch.models import BranchRef
from app.services.branch.mutations import BranchMutationService
from app.services.branch.policy import AuthorityPolicy
from app.services.branch.replace import BranchReplaceService
from app.services.demo.service import DemoService
from app.services.imports.service import ImportService
from app.services.read_models.inspection import InspectionReadService
from app.services.workflows.trash_restore import TrashRestoreService
from tests.service_helpers import branch_services


def reset_demo() -> dict:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    DemoService().reset()
    return DemoService().get_sample("core-cycle")


def test_branch_import_paths_and_promote_cleanup() -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])
    read_service = branch_services()
    mutation_service = BranchMutationService()
    replace_service = BranchReplaceService()

    result = mutation_service.apply(
        BranchRef.dev(sample["dev_version"]),
        {
            "kind": "import_batch",
            "import_batch_id": batch["import_batch_id"],
            "mark_as_candidate_release": True,
        },
    )
    statuses = {row["business_key"]: row["status"] for row in result["report_rows"]}
    assert statuses["rel.locked.same"] == "BOUND_EXISTING_VARIANT"
    assert statuses["rel.locked.changed"] == "CREATED_AND_BOUND_VARIANT"
    assert statuses["dev.mutable"] == "CREATED_AND_BOUND_VARIANT"
    assert statuses["dev.new.entry"] == "CREATED_AND_BOUND_VARIANT"

    preview = replace_service.preview(BranchRef.dev(sample["dev_version"]), BranchRef.rel_current())
    assert preview["source_branch_ref"] == f"dev/{sample['dev_version']}"
    assert preview["target_branch_ref"] == "rel/current"
    assert preview["target_entry_count"] >= 4

    replace_service.execute(BranchRef.dev(sample["dev_version"]), BranchRef.rel_current())
    rel_entries = read_service.list_branch_entries(BranchRef.rel_current())
    rel_keys = {item["business_key"] for item in rel_entries}
    assert {"rel.locked.same", "rel.locked.changed", "dev.mutable", "dev.new.entry"}.issubset(rel_keys)
    assert read_service.list_dev_branches(active_only=True) == []


def test_promote_rolls_back_when_cleanup_fails(monkeypatch) -> None:
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
            "mark_as_candidate_release": True,
        },
    )

    rel_keys_before = {item["business_key"] for item in read_service.list_branch_entries(BranchRef.rel_current())}
    dev_keys_before = {
        item["business_key"] for item in read_service.list_branch_entries(BranchRef.dev(sample["dev_version"]))
    }

    def fail_cleanup(*args, **kwargs):
        raise RuntimeError("promote cleanup failed")

    monkeypatch.setattr(replace_service.binding_commands, "remove_scope_binding_rows", fail_cleanup)

    with pytest.raises(RuntimeError, match="promote cleanup failed"):
        replace_service.execute(BranchRef.dev(sample["dev_version"]), BranchRef.rel_current())

    rel_keys_after = {item["business_key"] for item in read_service.list_branch_entries(BranchRef.rel_current())}
    dev_keys_after = {
        item["business_key"] for item in read_service.list_branch_entries(BranchRef.dev(sample["dev_version"]))
    }
    assert rel_keys_after == rel_keys_before
    assert dev_keys_after == dev_keys_before
    assert any(branch["version"] == sample["dev_version"] for branch in read_service.list_dev_branches(active_only=True))
    assert read_service.get_dev_branch(sample["dev_version"])["promoted_at"] is None


def test_direct_mutation_rolls_back_on_failure(monkeypatch) -> None:
    reset_demo()
    mutation_service = BranchMutationService()
    read_service = branch_services()
    original_bind_scope = mutation_service.bindings.bind_scope
    call_count = {"value": 0}

    def fail_on_second_bind(*args, **kwargs):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise RuntimeError("direct mutation failed")
        return original_bind_scope(*args, **kwargs)

    monkeypatch.setattr(mutation_service.bindings, "bind_scope", fail_on_second_bind)

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
    assert not any(branch["version"] == "2.4.3" for branch in read_service.list_dev_branches(active_only=True))


def test_import_batch_mutation_rolls_back_on_failure(monkeypatch) -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])
    mutation_service = BranchMutationService()
    read_service = branch_services()
    original_bind_scope = mutation_service.bindings.bind_scope
    call_count = {"value": 0}

    def fail_on_second_bind(*args, **kwargs):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise RuntimeError("import batch failed")
        return original_bind_scope(*args, **kwargs)

    monkeypatch.setattr(mutation_service.bindings, "bind_scope", fail_on_second_bind)

    with pytest.raises(RuntimeError, match="import batch failed"):
        mutation_service.apply(
            BranchRef.dev(sample["dev_version"]),
            {
                "kind": "import_batch",
                "import_batch_id": batch["import_batch_id"],
                "mark_as_candidate_release": True,
            },
        )

    assert read_service.entries.get_entry("dev.new.entry") is None
    assert not any(
        branch["version"] == sample["dev_version"] for branch in read_service.list_dev_branches(active_only=True)
    )


def test_release_hotfix_and_trash_restore_round_trip() -> None:
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

    before_delete = InspectionReadService().entry_variants("common.welcome")
    target_variant_id = before_delete["variants"][0]["variant_id"]
    delete_result = variant_service.delete(BranchRef.rel_current(), ["common.welcome"])
    assert delete_result["summary"]["trashed_variant_count"] == 1

    restore_result = variant_service.restore([target_variant_id])
    assert restore_result["summary"]["restored_count"] == 1

    after_restore = InspectionReadService().entry_variants("common.welcome")
    restored_variant = next(item for item in after_restore["variants"] if item["variant_id"] == target_variant_id)
    assert restored_variant["restored_at"] is not None


def test_delete_rolls_back_on_failure(monkeypatch) -> None:
    reset_demo()
    variant_service = TrashRestoreService()
    read_service = branch_services()

    def fail_trash_variant(*args, **kwargs):
        raise RuntimeError("trash delete failed")

    monkeypatch.setattr(variant_service.lifecycle, "trash_variant", fail_trash_variant)

    with pytest.raises(RuntimeError, match="trash delete failed"):
        variant_service.delete(BranchRef.rel_current(), ["common.welcome"])

    rel_keys = {item["business_key"] for item in read_service.list_branch_entries(BranchRef.rel_current())}
    assert "common.welcome" in rel_keys


def test_restore_rolls_back_on_failure(monkeypatch) -> None:
    reset_demo()
    variant_service = TrashRestoreService()
    inspection = InspectionReadService()

    target_variant_id = inspection.entry_variants("common.welcome")["variants"][0]["variant_id"]
    variant_service.delete(BranchRef.rel_current(), ["common.welcome"])

    def fail_refresh(*args, **kwargs):
        raise RuntimeError("restore refresh failed")

    monkeypatch.setattr(variant_service.lifecycle, "refresh_orphan_states", fail_refresh)

    with pytest.raises(RuntimeError, match="restore refresh failed"):
        variant_service.restore([target_variant_id])

    variant = next(
        item for item in inspection.entry_variants("common.welcome")["variants"] if item["variant_id"] == target_variant_id
    )
    assert variant["trashed_at"] is not None
    assert variant["restored_at"] is None


def test_restore_variants_reports_source_conflicts_and_continues() -> None:
    reset_demo()
    read_service = branch_services()
    variant_service = TrashRestoreService()
    inspection = InspectionReadService()

    conflicted_variant_id = inspection.entry_variants("common.welcome")["variants"][0]["variant_id"]
    variant_service.delete(BranchRef.rel_current(), ["common.welcome"])
    conflict_entry = read_service.entries.get_entry("common.welcome")
    assert conflict_entry is not None
    conflict_variant = read_service.catalog.get_variant(conflicted_variant_id)
    replacement_variant_id = read_service.catalog.create_variant(
        int(conflict_entry["entry_id"]),
        read_service.catalog.build_content(
            conflict_variant["file_name"],
            conflict_variant["source"],
            conflict_variant["translations"],
            conflict_variant["remarks"],
        ),
    )
    read_service.bindings.bind_scope(int(conflict_entry["entry_id"]), BranchRef.dev("2.4.1"), replacement_variant_id)

    restore_entry = read_service.entries.get_or_create_entry("restore.ok")
    restore_variant_id = read_service.catalog.create_variant(
        int(restore_entry["entry_id"]),
        read_service.catalog.build_content(
            "restore.xlsx",
            "Restore source",
            {"fr": "Restore target"},
            {"context": "restore"},
        ),
    )
    read_service.bindings.bind_scope(int(restore_entry["entry_id"]), BranchRef.rel_current(), restore_variant_id)
    variant_service.delete(BranchRef.rel_current(), ["restore.ok"])

    restore_result = variant_service.restore([conflicted_variant_id, restore_variant_id])
    statuses = {row["variant_id"]: row["status"] for row in restore_result["report_rows"]}

    assert restore_result["summary"]["restored_count"] == 1
    assert restore_result["summary"]["source_conflict_count"] == 1
    assert statuses[conflicted_variant_id] == "SOURCE_CONFLICT"
    assert statuses[restore_variant_id] == "RESTORED"
    assert read_service.catalog.get_variant(conflicted_variant_id)["trashed_at"] is not None
    assert read_service.catalog.get_variant(restore_variant_id)["restored_at"] is not None


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
    bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.2"), variant_id)

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

    assert result["report_rows"][0]["status"] == "BOUND_EXISTING_VARIANT"
    assert catalog.get_variant(variant_id)["translations"]["fr"] == "Series owner"


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
    service.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.2"), variant_id)

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
