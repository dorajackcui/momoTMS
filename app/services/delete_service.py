from __future__ import annotations

from typing import Any

from app.services.snapshot_service import SnapshotService


class DeleteService:
    def __init__(self) -> None:
        self.snapshots = SnapshotService()

    def delete_keys(self, branch: str, base_snapshot_id: int, keys: list[str]) -> dict[str, Any]:
        base_map = self.snapshots.get_snapshot_items(base_snapshot_id)
        to_delete = {key.strip() for key in keys if key and key.strip()}
        new_snapshot = self.snapshots.create_snapshot(
            branch,
            "delete_keys",
            parent_snapshot_id=base_snapshot_id,
            meta={"deleted_keys": sorted(to_delete)},
        )

        for key, item in base_map.items():
            if key not in to_delete:
                self.snapshots.set_item(new_snapshot, key, int(item["entry_id"]), item["src_hash"])

        deleted_keys = sorted(set(base_map) & to_delete)
        missing_keys = sorted(to_delete - set(base_map))
        report_rows: list[dict[str, Any]] = [
            {"key": key, "status": "DELETED"} for key in deleted_keys
        ] + [
            {"key": key, "status": "NOT_FOUND"} for key in missing_keys
        ]

        return {
            "snapshot_id": new_snapshot,
            "deleted_count": len(deleted_keys),
            "missing_count": len(missing_keys),
            "remaining_count": len(base_map) - len(deleted_keys),
            "report_rows": report_rows,
        }
