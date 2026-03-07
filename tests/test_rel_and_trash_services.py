from pathlib import Path

from app.db import DB_PATH
from app.services.demo_service import DemoService
from app.services.rel_service import RelService
from app.services.string_service import StringService
from app.services.trash_service import TrashService


def reset_demo() -> dict:
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
    demo = DemoService()
    demo.reset()
    return demo.get_sample("core-cycle")


def test_rel_hotfix_updates_canonical_content_and_trash_restore_roundtrip() -> None:
    sample = reset_demo()
    rel = RelService()
    strings = StringService()
    trash = TrashService()

    rel.active_hotfix(
        sample["active_hotfix"]["business_key"],
        sample["active_hotfix"]["lang"],
        sample["active_hotfix"]["target_text"],
    )
    active_target = strings.get_string(sample["active_hotfix"]["business_key"], include_deleted=False)
    assert active_target is not None
    assert active_target["translations"]["fr"] == sample["active_hotfix"]["target_text"]

    rel.passive_hotfix(
        sample["passive_hotfix"]["business_key"],
        sample["passive_hotfix"]["source"],
        sample["passive_hotfix"]["translations_by_lang"],
        sample["passive_hotfix"]["remarks_by_key"],
        file_name=sample["passive_hotfix"]["file_name"],
    )
    passive_target = strings.get_string(sample["passive_hotfix"]["business_key"], include_deleted=False)
    assert passive_target is not None
    assert passive_target["source"] == sample["passive_hotfix"]["source"]
    assert passive_target["translations"]["fr"] == sample["passive_hotfix"]["translations_by_lang"]["fr"]
    assert passive_target["remarks"]["context"] == sample["passive_hotfix"]["remarks_by_key"]["context"]

    delete_result = trash.delete(sample["trash_keys"])
    assert delete_result["summary"]["deleted_count"] == 1
    deleted = strings.get_string(sample["trash_keys"][0], include_deleted=True)
    assert deleted is not None
    assert deleted["deleted_at"] is not None

    restore_result = trash.restore(sample["trash_keys"])
    assert restore_result["summary"]["restored_count"] == 1
    restored = strings.get_string(sample["trash_keys"][0], include_deleted=False)
    assert restored is not None
    assert restored["deleted_at"] is None
