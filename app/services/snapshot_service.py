from __future__ import annotations

from typing import Any

from app.db import get_conn, json_dumps, json_loads
from app.services.utils import now_iso


class SnapshotService:
    def create_snapshot(
        self,
        branch: str,
        action_type: str,
        parent_snapshot_id: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> int:
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO snapshots(branch, parent_snapshot_id, action_type, created_at, meta_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (branch, parent_snapshot_id, action_type, now_iso(), json_dumps(meta or {})),
            )
            return int(cur.lastrowid)

    def copy_items(self, from_snapshot_id: int, to_snapshot_id: int) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO snapshot_items(snapshot_id, key, entry_id, src_hash)
                SELECT ?, key, entry_id, src_hash FROM snapshot_items WHERE snapshot_id = ?
                """,
                (to_snapshot_id, from_snapshot_id),
            )

    def set_item(self, snapshot_id: int, key: str, entry_id: int, src_hash: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO snapshot_items(snapshot_id, key, entry_id, src_hash)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(snapshot_id, key)
                DO UPDATE SET entry_id=excluded.entry_id, src_hash=excluded.src_hash
                """,
                (snapshot_id, key, entry_id, src_hash),
            )

    def get_snapshot_items(self, snapshot_id: int) -> dict[str, dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT si.key, si.entry_id, si.src_hash, e.src, e.version_tag
                FROM snapshot_items si
                JOIN entries e ON e.entry_id = si.entry_id
                WHERE si.snapshot_id = ?
                """,
                (snapshot_id,),
            ).fetchall()
        return {row["key"]: row for row in rows}

    def get_snapshot(self, snapshot_id: int) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if not row:
            return None
        snapshot = dict(row)
        snapshot["snapshot_id"] = int(snapshot["snapshot_id"])
        snapshot["parent_snapshot_id"] = (
            int(snapshot["parent_snapshot_id"]) if snapshot["parent_snapshot_id"] is not None else None
        )
        snapshot["meta"] = json_loads(snapshot.pop("meta_json"))
        snapshot["key_count"] = self.count_items(snapshot_id)
        return snapshot

    def count_items(self, snapshot_id: int) -> int:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM snapshot_items WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        return int(row["count"])
