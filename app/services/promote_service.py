from __future__ import annotations

from app.services.snapshot_service import SnapshotService


class PromoteService:
    def __init__(self) -> None:
        self.snapshots = SnapshotService()

    def promote(self, dev_last_snapshot_id: int, current_release_snapshot_id: int, release_version: str) -> dict[str, int]:
        dev_map = self.snapshots.get_snapshot_items(dev_last_snapshot_id)
        rel_map = self.snapshots.get_snapshot_items(current_release_snapshot_id)

        new_release = self.snapshots.create_snapshot(
            "release",
            "promote",
            parent_snapshot_id=current_release_snapshot_id,
            meta={
                "from_dev_snapshot": dev_last_snapshot_id,
                "release_version": release_version,
            },
        )

        added = 0
        conflict = 0
        carried = 0

        for key, dev_item in dev_map.items():
            if key in rel_map and rel_map[key]["src_hash"] != dev_item["src_hash"]:
                conflict += 1
                self.snapshots.set_item(new_release, key, int(rel_map[key]["entry_id"]), rel_map[key]["src_hash"])
            else:
                if key not in rel_map:
                    added += 1
                else:
                    carried += 1
                self.snapshots.set_item(new_release, key, int(dev_item["entry_id"]), dev_item["src_hash"])

        deprecated = len(set(rel_map.keys()) - set(dev_map.keys()))

        return {
            "snapshot_id": new_release,
            "target_key_count": len(dev_map),
            "added_count": added,
            "conflict_src_changed_count": conflict,
            "carried_over_count": carried,
            "deprecated_count": deprecated,
        }
