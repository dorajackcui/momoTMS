from pathlib import Path

from app.db import DB_PATH, get_conn, init_db
from app.services.archive_service import ArchiveService
from app.services.snapshot_service import SnapshotService
from app.services.utils import src_hash


def _seed_entry(key: str, src: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO entries(key, src, src_hash, version_tag, meta_json) VALUES (?, ?, ?, 'v', '{}')",
            (key, src, src_hash(src)),
        )
        return int(cur.lastrowid)


def test_archive_overwrites_master_on_src_conflict_and_keeps_master_only() -> None:
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
    init_db()
    snapshots = SnapshotService()
    release_snapshot = snapshots.create_snapshot("release", "seed")
    master_snapshot = snapshots.create_snapshot("master", "seed")

    archive_entry = _seed_entry("shared", "release src")
    master_conflict_entry = _seed_entry("shared", "master src")
    master_only_entry = _seed_entry("master_only", "master only")

    snapshots.set_item(release_snapshot, "shared", archive_entry, src_hash("release src"))
    snapshots.set_item(master_snapshot, "shared", master_conflict_entry, src_hash("master src"))
    snapshots.set_item(master_snapshot, "master_only", master_only_entry, src_hash("master only"))

    result = ArchiveService().archive(release_snapshot, master_snapshot)

    assert result["added_count"] == 0
    assert result["overwritten_count"] == 1
    assert result["kept_master_only_count"] == 1

    archived_items = snapshots.get_snapshot_items(result["snapshot_id"])
    assert archived_items["shared"]["src_hash"] == src_hash("release src")
    assert "master_only" in archived_items
