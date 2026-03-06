from __future__ import annotations

from typing import Any

from app.services.snapshot_service import SnapshotService


class PromoteService:
    def __init__(self) -> None:
        self.snapshots = SnapshotService()

    def preview(self, dev_last_snapshot_id: int, current_release_snapshot_id: int) -> dict[str, Any]:
        dev_map = self.snapshots.get_snapshot_items(dev_last_snapshot_id)
        rel_map = self.snapshots.get_snapshot_items(current_release_snapshot_id)

        added = 0
        conflict = 0
        carried = 0
        report_rows: list[dict[str, Any]] = []

        for key in sorted(dev_map):
            dev_item = dev_map[key]
            if key in rel_map and rel_map[key]["src_hash"] != dev_item["src_hash"]:
                conflict += 1
                report_rows.append({"key": key, "status": "CONFLICT_KEPT_RELEASE"})
            else:
                if key not in rel_map:
                    added += 1
                    report_rows.append({"key": key, "status": "ADDED"})
                else:
                    carried += 1
                    report_rows.append({"key": key, "status": "CARRIED"})

        deprecated_keys = sorted(set(rel_map.keys()) - set(dev_map.keys()))
        for key in deprecated_keys:
            report_rows.append({"key": key, "status": "DEPRECATED"})

        return {
            "target_key_count": len(dev_map),
            "added_count": added,
            "conflict_src_changed_count": conflict,
            "carried_over_count": carried,
            "deprecated_count": len(deprecated_keys),
            "report_rows": report_rows,
        }

    def promote(self, dev_last_snapshot_id: int, current_release_snapshot_id: int, release_version: str) -> dict[str, int]:
        preview = self.preview(dev_last_snapshot_id, current_release_snapshot_id)
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

        for key, dev_item in dev_map.items():
            if key in rel_map and rel_map[key]["src_hash"] != dev_item["src_hash"]:
                self.snapshots.set_item(new_release, key, int(rel_map[key]["entry_id"]), rel_map[key]["src_hash"])
            else:
                self.snapshots.set_item(new_release, key, int(dev_item["entry_id"]), dev_item["src_hash"])

        return {
            "snapshot_id": new_release,
            "target_key_count": preview["target_key_count"],
            "added_count": preview["added_count"],
            "conflict_src_changed_count": preview["conflict_src_changed_count"],
            "carried_over_count": preview["carried_over_count"],
            "deprecated_count": preview["deprecated_count"],
        }
