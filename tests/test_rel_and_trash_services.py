from pathlib import Path

from app.db import get_db_path
from app.services.demo.service import DemoService
from app.services.variant.compatibility import StringService
from app.services.variant.inspection import VariantInspectionService
from app.services.workflows.rel import RelService
from app.services.workflows.trash import TrashService


def reset_demo() -> dict:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    demo = DemoService()
    demo.reset()
    return demo.get_sample("core-cycle")


def test_rel_hotfix_updates_canonical_content() -> None:
    sample = reset_demo()
    rel = RelService()
    strings = StringService()
    active_target_text = "  Bienvenue hotfix {0}  "
    passive_source = "  Passive hotfix source updated  "
    passive_translations = {
        "fr": "  Correctif passif  ",
        "en": "",
    }
    passive_remarks = {
        "context": "  Passive hotfix updated from rel  ",
    }
    passive_file_name = "  release/common.xlsx  "

    rel.active_hotfix(
        sample["active_hotfix"]["business_key"],
        sample["active_hotfix"]["lang"],
        active_target_text,
    )
    active_target = strings.get_string(sample["active_hotfix"]["business_key"], include_deleted=False)
    assert active_target is not None
    assert active_target["translations"]["fr"] == active_target_text

    rel.passive_hotfix(
        sample["passive_hotfix"]["business_key"],
        passive_source,
        passive_translations,
        passive_remarks,
        file_name=passive_file_name,
    )
    inspection = VariantInspectionService().entry_variants(sample["passive_hotfix"]["business_key"])
    passive_target = strings.get_string(sample["passive_hotfix"]["business_key"], include_deleted=False)
    assert passive_target is not None
    assert passive_target["file_name"] == "release/common.xlsx"
    assert passive_target["source"] == "Passive hotfix source updated"
    assert passive_target["translations"]["fr"] == "  Correctif passif  "
    assert passive_target["translations"]["en"] == ""
    assert passive_target["remarks"]["context"] == "Passive hotfix updated from rel"
    assert len(inspection["variants"]) == 2
    assert any(variant["is_orphaned"] for variant in inspection["variants"])


def test_rel_source_hotfix_rebinds_rel_without_touching_dev_binding() -> None:
    reset_demo()
    strings = StringService()
    rel = RelService()
    inspection = VariantInspectionService()

    shared_variant_id = strings.create_string(
        "hotfix.shared",
        "release/shared.xlsx",
        "Shared source",
        {"fr": "Shared fr", "en": "Shared en"},
        {"context": "shared"},
    )
    strings.ensure_membership(shared_variant_id, "rel", "current")
    strings.ensure_membership(shared_variant_id, "dev", "2.2.3")

    result = rel.passive_hotfix(
        "hotfix.shared",
        "Shared source updated",
        {"fr": "Rel rewritten"},
        {"context": "rewritten"},
        file_name="release/shared-hotfix.xlsx",
    )

    assert result["summary"]["status"] == "CREATED_SOURCE_VARIANT"
    variants_payload = inspection.entry_variants("hotfix.shared")
    variants_by_source = {variant["source"]: variant for variant in variants_payload["variants"]}

    assert variants_by_source["Shared source updated"]["file_name"] == "release/shared-hotfix.xlsx"
    assert variants_by_source["Shared source updated"]["translations"]["fr"] == "Rel rewritten"
    assert {(binding["scope_type"], binding["scope_value"]) for binding in variants_by_source["Shared source updated"]["bindings"]} == {
        ("rel", "current")
    }
    assert {(binding["scope_type"], binding["scope_value"]) for binding in variants_by_source["Shared source"]["bindings"]} == {
        ("dev", "2.2.3")
    }


def test_trash_delete_is_scope_aware_and_restore_is_variant_aware() -> None:
    reset_demo()
    strings = StringService()
    trash = TrashService()

    string_id = strings.get_string("common.welcome", include_deleted=True)["string_id"]
    strings.ensure_membership(string_id, "dev", "2.2.3")

    delete_result = trash.delete("dev/2.2.3", ["common.welcome", "missing.key"])
    assert delete_result["summary"] == {
        "scope_ref": "dev/2.2.3",
        "trashed_variant_count": 0,
        "removed_scope_binding_count": 1,
        "not_bound_count": 0,
        "missing_count": 1,
    }
    statuses = {row.get("business_key", row.get("variant_id")): row["status"] for row in delete_result["report_rows"]}
    assert statuses["common.welcome"] == "REMOVED_SCOPE_BINDING"
    assert statuses["missing.key"] == "MISSING"

    after_delete = strings.get_string("common.welcome", include_deleted=True)
    assert after_delete is not None
    assert after_delete["deleted_at"] is None
    assert any(
        item["membership_type"] == "rel" and item["membership_value"] == "current"
        for item in after_delete["memberships"]
    )
    assert all(
        not (item["membership_type"] == "dev" and item["membership_value"] == "2.2.3")
        for item in after_delete["memberships"]
    )

    second_delete = trash.delete("rel/current", ["common.welcome"])
    assert second_delete["summary"]["trashed_variant_count"] == 1
    deleted_view = strings.get_string("common.welcome", include_deleted=True)
    assert deleted_view is not None
    assert deleted_view["deleted_at"] is not None

    restore_result = trash.restore([deleted_view["string_id"], 999999])
    assert restore_result["summary"] == {
        "restored_count": 1,
        "not_trashed_count": 0,
        "missing_count": 1,
    }
    restore_statuses = {row.get("business_key", row.get("variant_id")): row["status"] for row in restore_result["report_rows"]}
    assert restore_statuses["common.welcome"] == "RESTORED"
    assert restore_statuses[999999] == "MISSING"

    restored_view = strings.get_string("common.welcome", include_deleted=False)
    assert restored_view is not None
    assert restored_view["deleted_at"] is None
    assert restored_view["restored_at"] is not None
