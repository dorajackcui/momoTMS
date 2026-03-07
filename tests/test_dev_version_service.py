from pathlib import Path

from app.db import DB_PATH
from app.services.demo_service import DemoService
from app.services.dev_version_service import DevVersionService
from app.services.import_service import ImportService
from app.services.string_service import StringService


def reset_demo() -> dict:
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
    demo = DemoService()
    demo.reset()
    return demo.get_sample("core-cycle")


def test_dev_import_creates_updates_tags_and_protects_rel_strings() -> None:
    sample = reset_demo()
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    result = DevVersionService().import_batch(batch["import_batch_id"], sample["dev_version"])

    assert result["summary"]["created_count"] == 1
    assert result["summary"]["updated_canonical_count"] == 1
    assert result["summary"]["tagged_only_count"] == 1
    assert result["summary"]["protected_skipped_count"] == 1

    statuses = {row["business_key"]: row["status"] for row in result["report_rows"]}
    assert statuses["rel.locked.same"] == "TAGGED_ONLY"
    assert statuses["rel.locked.changed"] == "PROTECTED_SKIPPED"
    assert statuses["dev.mutable"] == "UPDATED_CANONICAL"
    assert statuses["dev.new.entry"] == "CREATED"

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

    assert created is not None
    assert created["source"] == "New source from dev"
