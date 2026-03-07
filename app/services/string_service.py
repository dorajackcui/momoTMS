from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import get_conn
from app.services.project_service import DEFAULT_PROJECT_ID
from app.services.utils import now_iso


class StringService:
    def list_strings(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        search: str | None = None,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [project_id]
        where = ["project_id = ?"]
        if not include_deleted:
            where.append("deleted_at IS NULL")
        if search:
            needle = f"%{search}%"
            where.append(
                "(business_key LIKE ? OR source LIKE ? OR COALESCE(file_name, '') LIKE ?)"
            )
            params.extend([needle, needle, needle])
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM strings
                WHERE {' AND '.join(where)}
                ORDER BY business_key
                """,
                params,
            ).fetchall()
        return self._hydrate_rows(rows)

    def get_string(
        self,
        business_key: str,
        project_id: int = DEFAULT_PROJECT_ID,
        include_deleted: bool = True,
    ) -> dict[str, Any] | None:
        params: list[Any] = [project_id, business_key]
        where = ["project_id = ?", "business_key = ?"]
        if not include_deleted:
            where.append("deleted_at IS NULL")
        with get_conn() as conn:
            row = conn.execute(
                f"""
                SELECT *
                FROM strings
                WHERE {' AND '.join(where)}
                LIMIT 1
                """,
                params,
            ).fetchone()
        if not row:
            return None
        return self._hydrate_rows([row])[0]

    def create_string(
        self,
        business_key: str,
        file_name: str | None,
        source: str,
        translations: dict[str, str | None],
        remarks: dict[str, str | None],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> int:
        timestamp = now_iso()
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO strings(
                    project_id,
                    business_key,
                    file_name,
                    source,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (project_id, business_key, file_name, source, timestamp, timestamp),
            )
            string_id = int(cur.lastrowid)
        self.replace_translations(string_id, translations)
        self.replace_remarks(string_id, remarks)
        return string_id

    def update_canonical(
        self,
        string_id: int,
        file_name: str | None,
        source: str,
        translations: dict[str, str | None],
        remarks: dict[str, str | None],
        restore_if_deleted: bool = False,
    ) -> None:
        timestamp = now_iso()
        with get_conn() as conn:
            if restore_if_deleted:
                conn.execute(
                    """
                    UPDATE strings
                    SET file_name = ?,
                        source = ?,
                        deleted_at = NULL,
                        trash_until = NULL,
                        restored_at = ?,
                        updated_at = ?
                    WHERE string_id = ?
                    """,
                    (file_name, source, timestamp, timestamp, string_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE strings
                    SET file_name = ?,
                        source = ?,
                        updated_at = ?
                    WHERE string_id = ?
                    """,
                    (file_name, source, timestamp, string_id),
                )
        self.replace_translations(string_id, translations)
        self.replace_remarks(string_id, remarks)

    def replace_translations(self, string_id: int, translations: dict[str, str | None]) -> None:
        timestamp = now_iso()
        with get_conn() as conn:
            for lang, target_text in translations.items():
                conn.execute(
                    """
                    INSERT INTO string_translations(string_id, lang, target_text, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(string_id, lang)
                    DO UPDATE SET
                        target_text = excluded.target_text,
                        updated_at = excluded.updated_at
                    """,
                    (string_id, lang, target_text, timestamp),
                )

    def replace_remarks(self, string_id: int, remarks: dict[str, str | None]) -> None:
        timestamp = now_iso()
        with get_conn() as conn:
            for remark_key, remark_value in remarks.items():
                conn.execute(
                    """
                    INSERT INTO string_remarks(string_id, remark_key, remark_value, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(string_id, remark_key)
                    DO UPDATE SET
                        remark_value = excluded.remark_value,
                        updated_at = excluded.updated_at
                    """,
                    (string_id, remark_key, remark_value, timestamp),
                )

    def ensure_membership(self, string_id: int, membership_type: str, membership_value: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO string_memberships(
                    string_id,
                    membership_type,
                    membership_value,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (string_id, membership_type, membership_value, now_iso()),
            )

    def has_membership(self, string_id: int, membership_type: str, membership_value: str) -> bool:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM string_memberships
                WHERE string_id = ? AND membership_type = ? AND membership_value = ?
                LIMIT 1
                """,
                (string_id, membership_type, membership_value),
            ).fetchone()
        return row is not None

    def get_membership_strings(
        self,
        membership_type: str,
        membership_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT s.*
                FROM strings s
                JOIN string_memberships sm ON sm.string_id = s.string_id
                WHERE s.project_id = ?
                  AND s.deleted_at IS NULL
                  AND sm.membership_type = ?
                  AND sm.membership_value = ?
                ORDER BY s.business_key
                """,
                (project_id, membership_type, membership_value),
            ).fetchall()
        return self._hydrate_rows(rows)

    def membership_count(
        self,
        membership_type: str,
        membership_value: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> int:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM strings s
                JOIN string_memberships sm ON sm.string_id = s.string_id
                WHERE s.project_id = ?
                  AND s.deleted_at IS NULL
                  AND sm.membership_type = ?
                  AND sm.membership_value = ?
                """,
                (project_id, membership_type, membership_value),
            ).fetchone()
        return int(row["count"] or 0)

    def clear_rel_memberships(self, project_id: int = DEFAULT_PROJECT_ID) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                DELETE FROM string_memberships
                WHERE membership_type = 'rel'
                  AND string_id IN (
                    SELECT string_id FROM strings WHERE project_id = ?
                  )
                """,
                (project_id,),
            )

    def remove_dev_memberships(
        self,
        versions: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> int:
        if not versions:
            return 0
        placeholders = ", ".join("?" for _ in versions)
        membership_params = [*versions, project_id]
        with get_conn() as conn:
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM string_memberships
                WHERE membership_type = 'dev'
                  AND membership_value IN ({placeholders})
                  AND string_id IN (
                    SELECT string_id FROM strings WHERE project_id = ?
                  )
                """,
                membership_params,
            ).fetchone()
            removed_count = int(row["count"] or 0)
            conn.execute(
                f"""
                DELETE FROM string_memberships
                WHERE membership_type = 'dev'
                  AND membership_value IN ({placeholders})
                  AND string_id IN (
                    SELECT string_id FROM strings WHERE project_id = ?
                  )
                """,
                membership_params,
            )
        return removed_count

    def soft_delete(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
        trash_days: int = 30,
    ) -> dict[str, list[str]]:
        if not business_keys:
            return {"deleted": [], "already_deleted": [], "missing": []}
        placeholders = ", ".join("?" for _ in business_keys)
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT string_id, business_key, deleted_at
                FROM strings
                WHERE project_id = ? AND business_key IN ({placeholders})
                """,
                [project_id, *business_keys],
            ).fetchall()
            found_by_key = {row["business_key"]: row for row in rows}
            missing = sorted(set(business_keys) - set(found_by_key))
            deleted: list[str] = []
            already_deleted: list[str] = []
            timestamp = now_iso()
            trash_until = self._trash_until(trash_days)
            for key in business_keys:
                row = found_by_key.get(key)
                if not row:
                    continue
                if row["deleted_at"]:
                    already_deleted.append(key)
                    continue
                conn.execute(
                    """
                    UPDATE strings
                    SET deleted_at = ?,
                        trash_until = ?,
                        updated_at = ?
                    WHERE string_id = ?
                    """,
                    (timestamp, trash_until, timestamp, int(row["string_id"])),
                )
                deleted.append(key)
        return {
            "deleted": sorted(deleted),
            "already_deleted": sorted(already_deleted),
            "missing": missing,
        }

    def restore(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, list[str]]:
        if not business_keys:
            return {"restored": [], "not_deleted": [], "missing": []}
        placeholders = ", ".join("?" for _ in business_keys)
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT string_id, business_key, deleted_at
                FROM strings
                WHERE project_id = ? AND business_key IN ({placeholders})
                """,
                [project_id, *business_keys],
            ).fetchall()
            found_by_key = {row["business_key"]: row for row in rows}
            missing = sorted(set(business_keys) - set(found_by_key))
            restored: list[str] = []
            not_deleted: list[str] = []
            timestamp = now_iso()
            for key in business_keys:
                row = found_by_key.get(key)
                if not row:
                    continue
                if not row["deleted_at"]:
                    not_deleted.append(key)
                    continue
                conn.execute(
                    """
                    UPDATE strings
                    SET deleted_at = NULL,
                        trash_until = NULL,
                        restored_at = ?,
                        updated_at = ?
                    WHERE string_id = ?
                    """,
                    (timestamp, timestamp, int(row["string_id"])),
                )
                restored.append(key)
        return {
            "restored": sorted(restored),
            "not_deleted": sorted(not_deleted),
            "missing": missing,
        }

    def trash_count(self, project_id: int = DEFAULT_PROJECT_ID) -> int:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM strings
                WHERE project_id = ? AND deleted_at IS NOT NULL
                """,
                (project_id,),
            ).fetchone()
        return int(row["count"] or 0)

    def _hydrate_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return []
        string_ids = [int(row["string_id"]) for row in rows]
        placeholders = ", ".join("?" for _ in string_ids)
        with get_conn() as conn:
            translations = conn.execute(
                f"""
                SELECT string_id, lang, target_text
                FROM string_translations
                WHERE string_id IN ({placeholders})
                ORDER BY lang
                """,
                string_ids,
            ).fetchall()
            remarks = conn.execute(
                f"""
                SELECT string_id, remark_key, remark_value
                FROM string_remarks
                WHERE string_id IN ({placeholders})
                ORDER BY remark_key
                """,
                string_ids,
            ).fetchall()
            memberships = conn.execute(
                f"""
                SELECT string_id, membership_type, membership_value
                FROM string_memberships
                WHERE string_id IN ({placeholders})
                ORDER BY membership_type, membership_value
                """,
                string_ids,
            ).fetchall()
        translations_by_id: dict[int, dict[str, str | None]] = defaultdict(dict)
        for row in translations:
            translations_by_id[int(row["string_id"])][row["lang"]] = row["target_text"]
        remarks_by_id: dict[int, dict[str, str | None]] = defaultdict(dict)
        for row in remarks:
            remarks_by_id[int(row["string_id"])][row["remark_key"]] = row["remark_value"]
        memberships_by_id: dict[int, list[dict[str, str]]] = defaultdict(list)
        for row in memberships:
            memberships_by_id[int(row["string_id"])].append(
                {
                    "membership_type": row["membership_type"],
                    "membership_value": row["membership_value"],
                }
            )
        hydrated: list[dict[str, Any]] = []
        for row in rows:
            string_id = int(row["string_id"])
            hydrated.append(
                {
                    "string_id": string_id,
                    "project_id": int(row["project_id"]),
                    "business_key": row["business_key"],
                    "file_name": row["file_name"],
                    "source": row["source"],
                    "translations": translations_by_id.get(string_id, {}),
                    "remarks": remarks_by_id.get(string_id, {}),
                    "memberships": memberships_by_id.get(string_id, []),
                    "deleted_at": row["deleted_at"],
                    "trash_until": row["trash_until"],
                    "restored_at": row["restored_at"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return hydrated

    def _trash_until(self, days: int) -> str:
        return (
            datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=days)
        ).isoformat()
