from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path("data/tms.db")


def _dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS entries (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                src TEXT NOT NULL,
                src_hash TEXT NOT NULL,
                version_tag TEXT,
                meta_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_entries_key_src_hash ON entries(key, src_hash);

            CREATE TABLE IF NOT EXISTS translations (
                entry_id INTEGER NOT NULL,
                lang TEXT NOT NULL,
                target_text TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (entry_id, lang),
                FOREIGN KEY (entry_id) REFERENCES entries(entry_id)
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch TEXT NOT NULL,
                parent_snapshot_id INTEGER,
                action_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                meta_json TEXT NOT NULL,
                FOREIGN KEY (parent_snapshot_id) REFERENCES snapshots(snapshot_id)
            );

            CREATE TABLE IF NOT EXISTS snapshot_items (
                snapshot_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                entry_id INTEGER NOT NULL,
                src_hash TEXT NOT NULL,
                PRIMARY KEY (snapshot_id, key),
                FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id),
                FOREIGN KEY (entry_id) REFERENCES entries(entry_id)
            );

            CREATE TABLE IF NOT EXISTS imports (
                import_batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                meta_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS import_rows (
                import_batch_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                sheet_name TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                key TEXT,
                src_hash TEXT,
                status TEXT NOT NULL,
                message TEXT,
                PRIMARY KEY (import_batch_id, file_path, sheet_name, row_index),
                FOREIGN KEY (import_batch_id) REFERENCES imports(import_batch_id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = _dict_factory
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)
