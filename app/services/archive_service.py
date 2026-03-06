from __future__ import annotations

from typing import Any

from app.services.snapshot_service import SnapshotService


class ArchiveService:
    def __init__(self) -> None:
        self.snapshots = SnapshotService()

    def archive(self, release_snapshot_id: int, master_snapshot_id: int) -> dict[str, Any]:
        release_map = self.snapshots.get_snapshot_items(release_snapshot_id)
        master_map = self.snapshots.get_snapshot_items(master_snapshot_id)

        new_master = self.snapshots.create_snapshot(
            "master",
            "archive_release",
            parent_snapshot_id=master_snapshot_id,
            meta={
                "archived_release_snapshot_id": release_snapshot_id,
            },
        )
        self.snapshots.copy_items(master_snapshot_id, new_master)

        added = 0
        overwritten = 0
        report_rows: list[dict[str, Any]] = []

        for key in sorted(release_map):
            release_item = release_map[key]
            if key in master_map:
                if master_map[key]["src_hash"] != release_item["src_hash"]:
                    overwritten += 1
                    status = "OVERWROTE_MASTER"
                else:
                    status = "REFRESHED_MATCHING"
            else:
                added += 1
                status = "ADDED_FROM_RELEASE"
            self.snapshots.set_item(new_master, key, int(release_item["entry_id"]), release_item["src_hash"])
            report_rows.append({"key": key, "status": status})

        master_only_keys = sorted(set(master_map) - set(release_map))
        for key in master_only_keys:
            report_rows.append({"key": key, "status": "KEPT_MASTER_ONLY"})

        return {
            "snapshot_id": new_master,
            "archived_key_count": len(release_map),
            "added_count": added,
            "overwritten_count": overwritten,
            "kept_master_only_count": len(master_only_keys),
            "total_key_count": len(set(release_map) | set(master_map)),
            "report_rows": report_rows,
        }
