from __future__ import annotations

from app.db import get_conn
from app.services.utils import now_iso


class BranchService:
    def get_head(self, branch: str) -> int | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT snapshot_id FROM branch_heads WHERE branch = ?",
                (branch,),
            ).fetchone()
        if not row or row["snapshot_id"] is None:
            return None
        return int(row["snapshot_id"])

    def set_head(self, branch: str, snapshot_id: int | None) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO branch_heads(branch, snapshot_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(branch)
                DO UPDATE SET snapshot_id=excluded.snapshot_id, updated_at=excluded.updated_at
                """,
                (branch, snapshot_id, now_iso()),
            )

    def list_heads(self) -> dict[str, int | None]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT branch, snapshot_id FROM branch_heads ORDER BY branch",
            ).fetchall()
        return {
            row["branch"]: int(row["snapshot_id"]) if row["snapshot_id"] is not None else None
            for row in rows
        }
