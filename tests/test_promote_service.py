from pathlib import Path

from app.db import get_db_path
from app.services.demo.service import DemoService
from app.services.imports.service import ImportService
from app.services.variant.compatibility import StringService
from app.services.workflows.dev_versions import DevVersionService
from app.services.workflows.promote import PromoteService


def reset_demo() -> dict:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    demo = DemoService()
    demo.reset()
    return demo.get_sample("core-cycle")


def test_promote_switches_rel_memberships_and_cleans_dev_line_tags() -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])
    DevVersionService().import_batch(batch["import_batch_id"], sample["dev_version"])

    preview = PromoteService().preview(sample["dev_version"])
    assert preview["target_key_count"] == 4
    assert preview["added_to_rel_count"] == 2
    assert preview["already_in_rel_count"] == 2
    assert preview["removed_from_rel_count"] == 3
    assert preview["cleanup_dev_membership_count"] == 4

    result = PromoteService().execute(sample["dev_version"])
    assert result["summary"]["cleaned_dev_membership_count"] == 4

    strings = StringService()
    rel_members = strings.get_membership_strings("rel", "current")
    rel_keys = {item["business_key"] for item in rel_members}
    assert rel_keys == {
        "rel.locked.same",
        "rel.locked.changed",
        "dev.mutable",
        "dev.new.entry",
    }

    assert DevVersionService().list_versions(active_only=True) == []
    assert strings.membership_count("dev", sample["dev_version"]) == 0

    retained_members = strings.get_membership_strings("retained", "retained")
    retained_keys = {item["business_key"] for item in retained_members}
    assert "common.welcome" in retained_keys
    assert "fill.rel" in retained_keys
    assert "hotfix.passive" in retained_keys

    retained_string = strings.get_string("common.welcome", include_deleted=False)
    assert retained_string is not None
    assert any(
        item["membership_type"] == "retained" and item["membership_value"] == "retained"
        for item in retained_string["memberships"]
    )


def test_promote_cleans_all_versions_in_same_version_line() -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])
    service = DevVersionService()
    service.import_batch(batch["import_batch_id"], "2.2.3", mark_as_candidate=False)
    service.import_batch(batch["import_batch_id"], "2.2.4", mark_as_candidate=True)

    preview = PromoteService().preview("2.2.4")
    assert preview["cleanup_dev_membership_count"] == 8

    result = PromoteService().execute("2.2.4")
    assert result["summary"]["cleaned_dev_membership_count"] == 8
    assert service.list_versions(active_only=True) == []
