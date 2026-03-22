from __future__ import annotations

import sqlite3
from typing import Any

from app.db import get_conn
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.utils import now_iso
from app.services.variant.normalization import normalize_business_keys, require_non_content_value
from app.services.variant.records import EntryRecord


class EntryRepository:
    def get_by_business_key(
        self,
        project_id: int,
        business_key: str,
        conn: sqlite3.Connection | None = None,
    ) -> EntryRecord | None:
        if conn is not None:
            row = conn.execute(
                """
                SELECT *
                FROM entries
                WHERE project_id = ? AND business_key = ?
                LIMIT 1
                """,
                (project_id, business_key),
            ).fetchone()
        else:
            with get_conn() as local_conn:
                row = local_conn.execute(
                    """
                    SELECT *
                    FROM entries
                    WHERE project_id = ? AND business_key = ?
                    LIMIT 1
                    """,
                    (project_id, business_key),
                ).fetchone()
        if not row:
            return None
        return self._hydrate_rows([row])[0]

    def get_by_id(self, entry_id: int, conn: sqlite3.Connection | None = None) -> EntryRecord | None:
        if conn is not None:
            row = conn.execute(
                "SELECT * FROM entries WHERE entry_id = ? LIMIT 1",
                (entry_id,),
            ).fetchone()
        else:
            with get_conn() as local_conn:
                row = local_conn.execute(
                    "SELECT * FROM entries WHERE entry_id = ? LIMIT 1",
                    (entry_id,),
                ).fetchone()
        if not row:
            return None
        return self._hydrate_rows([row])[0]

    def create(
        self,
        project_id: int,
        business_key: str,
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> EntryRecord:
        if conn is not None:
            cur = conn.execute(
                """
                INSERT INTO entries(project_id, business_key, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (project_id, business_key, timestamp, timestamp),
            )
            row = conn.execute(
                "SELECT * FROM entries WHERE entry_id = ?",
                (int(cur.lastrowid),),
            ).fetchone()
        else:
            with get_conn() as local_conn:
                cur = local_conn.execute(
                    """
                    INSERT INTO entries(project_id, business_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (project_id, business_key, timestamp, timestamp),
                )
                row = local_conn.execute(
                    "SELECT * FROM entries WHERE entry_id = ?",
                    (int(cur.lastrowid),),
                ).fetchone()
        return self._hydrate_rows([row])[0]

    def insert_many_ignore(
        self,
        project_id: int,
        business_keys: list[str],
        timestamp: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if not business_keys:
            return
        if conn is not None:
            conn.executemany(
                """
                INSERT OR IGNORE INTO entries(project_id, business_key, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                [(project_id, key, timestamp, timestamp) for key in business_keys],
            )
            return
        with get_conn() as local_conn:
            local_conn.executemany(
                """
                INSERT OR IGNORE INTO entries(project_id, business_key, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                [(project_id, key, timestamp, timestamp) for key in business_keys],
            )

    def get_by_keys(
        self,
        project_id: int,
        business_keys: list[str],
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, EntryRecord]:
        if not business_keys:
            return {}
        placeholders = ", ".join("?" for _ in business_keys)
        if conn is not None:
            rows = conn.execute(
                f"""
                SELECT *
                FROM entries
                WHERE project_id = ? AND business_key IN ({placeholders})
                """,
                [project_id, *business_keys],
            ).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(
                    f"""
                    SELECT *
                    FROM entries
                    WHERE project_id = ? AND business_key IN ({placeholders})
                    """,
                    [project_id, *business_keys],
                ).fetchall()
        hydrated = self._hydrate_rows(rows)
        return {entry["business_key"]: entry for entry in hydrated}

    def list(self, project_id: int, search: str | None = None) -> list[EntryRecord]:
        params: list[Any] = [project_id]
        where = ["e.project_id = ?"]
        if search:
            needle = f"%{require_non_content_value('search', search)}%"
            where.append(
                """
                (
                    e.business_key LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM variants v
                        WHERE v.entry_id = e.entry_id
                          AND (COALESCE(v.source, '') LIKE ? OR COALESCE(v.file_name, '') LIKE ?)
                    )
                )
                """
            )
            params.extend([needle, needle, needle])
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT e.*
                FROM entries e
                WHERE {' AND '.join(where)}
                ORDER BY e.business_key
                """,
                params,
            ).fetchall()
        return self._hydrate_rows(rows)

    def _hydrate_rows(self, rows: list[dict[str, Any]]) -> list[EntryRecord]:
        return [
            {
                "entry_id": int(row["entry_id"]),
                "project_id": int(row["project_id"]),
                "business_key": row["business_key"].strip(),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]


class EntryService:
    def __init__(self, entries: EntryRepository | None = None) -> None:
        self._entries = entries or EntryRepository()

    def get_or_create_entry(
        self,
        business_key: str,
        project_id: int = DEFAULT_PROJECT_ID,
        conn: sqlite3.Connection | None = None,
    ) -> EntryRecord:
        normalized_key = require_non_content_value("business_key", business_key)
        entry = self._entries.get_by_business_key(project_id, normalized_key, conn=conn)
        if entry is not None:
            return entry
        return self._entries.create(project_id, normalized_key, now_iso(), conn=conn)

    def get_entry(
        self,
        business_key: str,
        project_id: int = DEFAULT_PROJECT_ID,
        conn: sqlite3.Connection | None = None,
    ) -> EntryRecord | None:
        normalized_key = require_non_content_value("business_key", business_key)
        return self._entries.get_by_business_key(project_id, normalized_key, conn=conn)

    def get_entry_by_id(self, entry_id: int, conn: sqlite3.Connection | None = None) -> EntryRecord | None:
        return self._entries.get_by_id(entry_id, conn=conn)

    def ensure_entries(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, EntryRecord]:
        normalized_keys = normalize_business_keys(business_keys)
        if not normalized_keys:
            return {}
        existing = self._entries.get_by_keys(project_id, normalized_keys, conn=conn)
        missing_keys = [key for key in normalized_keys if key not in existing]
        if missing_keys:
            self._entries.insert_many_ignore(project_id, missing_keys, now_iso(), conn=conn)
        return self._entries.get_by_keys(project_id, normalized_keys, conn=conn)

    def get_entries_by_keys(
        self,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, EntryRecord]:
        normalized_keys = normalize_business_keys(business_keys)
        return self._entries.get_by_keys(project_id, normalized_keys, conn=conn)

    def list_entries(
        self,
        project_id: int = DEFAULT_PROJECT_ID,
        search: str | None = None,
    ) -> list[EntryRecord]:
        return self._entries.list(project_id, search=search)
