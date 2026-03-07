from pathlib import Path

from app.db import DB_PATH
from app.services.demo.service import DemoService
from app.services.variant.compatibility import StringService
from app.services.workflows.rel import RelService
from app.services.workflows.trash import TrashService


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
    passive_target = strings.get_string(sample["passive_hotfix"]["business_key"], include_deleted=False)
    assert passive_target is not None
    assert passive_target["file_name"] == "release/common.xlsx"
    assert passive_target["source"] == "Passive hotfix source updated"
    assert passive_target["translations"]["fr"] == "  Correctif passif  "
    assert passive_target["translations"]["en"] == ""
    assert passive_target["remarks"]["context"] == "Passive hotfix updated from rel"

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
