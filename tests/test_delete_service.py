from pathlib import Path

from app.db import DB_PATH, get_conn, init_db
from app.services.delete_service import DeleteService
from app.services.snapshot_service import SnapshotService
from app.services.utils import src_hash


def _seed_entry(key: str, src: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO entries(key, src, src_hash, version_tag, meta_json) VALUES (?, ?, ?, 'v', '{}')",
            (key, src, src_hash(src)),
        )
        return int(cur.lastrowid)


def test_delete_keys_removes_hits_and_reports_misses() -> None:
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
    init_db()
    snapshots = SnapshotService()
    release_snapshot = snapshots.create_snapshot("release", "seed")

    keep_entry = _seed_entry("keep", "Keep me")
    delete_entry = _seed_entry("delete", "Delete me")
    snapshots.set_item(release_snapshot, "keep", keep_entry, src_hash("Keep me"))
    snapshots.set_item(release_snapshot, "delete", delete_entry, src_hash("Delete me"))

    result = DeleteService().delete_keys("release", release_snapshot, ["delete", "missing"])

    assert result["deleted_count"] == 1
    assert result["missing_count"] == 1
    assert result["remaining_count"] == 1

    new_items = snapshots.get_snapshot_items(result["snapshot_id"])
    assert "keep" in new_items
    assert "delete" not in new_items
