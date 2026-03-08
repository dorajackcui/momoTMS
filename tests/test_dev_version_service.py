from pathlib import Path

from app.db import get_db_path
from app.services.demo.service import DemoService
from app.services.imports.service import ImportService
from app.services.variant.compatibility import StringService
from app.services.workflows.dev_versions import DevVersionService


def reset_demo() -> dict:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    demo = DemoService()
    demo.reset()
    return demo.get_sample("core-cycle")


def test_dev_import_creates_updates_tags_and_protects_rel_strings() -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    result = DevVersionService().import_batch(batch["import_batch_id"], sample["dev_version"])

    assert result["summary"]["created_entry_count"] == 1
    assert result["summary"]["created_source_variant_count"] == 3
    assert result["summary"]["bound_rel_owned_source_variant_count"] == 1
    assert result["summary"]["updated_reused_source_variant_count"] == 0
    assert result["summary"]["revived_orphan_source_variant_count"] == 0
    assert result["summary"]["processed_count"] == 4

    statuses = {row["business_key"]: row["status"] for row in result["report_rows"]}
    assert statuses["rel.locked.same"] == "BOUND_REL_OWNED_SOURCE_VARIANT"
    assert statuses["rel.locked.changed"] == "CREATED_SOURCE_VARIANT"
    assert statuses["dev.mutable"] == "CREATED_SOURCE_VARIANT"
    assert statuses["dev.new.entry"] == "CREATED_SOURCE_VARIANT"

    strings = StringService()
    mutable = strings.get_string("dev.mutable", include_deleted=False)
    protected = strings.get_string("rel.locked.changed", include_deleted=False)
    created = strings.get_string("dev.new.entry", include_deleted=False)

    assert mutable is not None
    assert mutable["source"] == "Mutable source updated"
    assert any(item["membership_type"] == "dev" and item["membership_value"] == sample["dev_version"] for item in mutable["memberships"])

    assert protected is not None
    assert protected["source"] == "Release protected source"
    assert any(item["membership_type"] == "dev" and item["membership_value"] == sample["dev_version"] for item in protected["memberships"])
    rel_members = strings.get_membership_strings("rel", "current")
    assert any(item["business_key"] == "rel.locked.changed" for item in rel_members)

    assert created is not None
    assert created["source"] == "New source from dev"
