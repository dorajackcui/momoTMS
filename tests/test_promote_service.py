from pathlib import Path

from app.db import DB_PATH
from app.services.demo_service import DemoService
from app.services.dev_version_service import DevVersionService
from app.services.import_service import ImportService
from app.services.promote_service import PromoteService
from app.services.string_service import StringService


def reset_demo() -> dict:
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
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
