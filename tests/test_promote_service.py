from pathlib import Path

from app.db import DB_PATH, get_conn, init_db
from app.services.promote_service import PromoteService
from app.services.snapshot_service import SnapshotService


def _seed_entry(key: str, src: str, src_hash: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO entries(key, src, src_hash, version_tag, meta_json) VALUES (?, ?, ?, 'v', '{}')",
            (key, src, src_hash),
        )
        return int(cur.lastrowid)


def test_promote_keeps_release_when_src_conflicts() -> None:
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
    init_db()
    snap = SnapshotService()
    release_prev = snap.create_snapshot("release", "seed")
    dev_last = snap.create_snapshot("dev", "seed")

    e_rel = _seed_entry("k1", "old", "h_old")
    e_dev = _seed_entry("k1", "new", "h_new")
    e_dev2 = _seed_entry("k2", "stable", "h_stable")

    snap.set_item(release_prev, "k1", e_rel, "h_old")
    snap.set_item(dev_last, "k1", e_dev, "h_new")
    snap.set_item(dev_last, "k2", e_dev2, "h_stable")

    report = PromoteService().promote(dev_last, release_prev, "2.4.x")

    assert report["target_key_count"] == 2
    assert report["conflict_src_changed_count"] == 1
    assert report["added_count"] == 1
    assert report["carried_over_count"] == 0
