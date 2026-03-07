from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path("data/tms.db")
SCHEMA_VERSION = "canonical-v2"


def _dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = _dict_factory
        conn.execute("PRAGMA foreign_keys = ON")
        if _current_schema_version(conn) != SCHEMA_VERSION:
            _rebuild_schema(conn)
    finally:
        conn.close()


def _current_schema_version(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'app_meta'"
    ).fetchone()
    if not row:
        return None
    version_row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'schema_version'"
    ).fetchone()
    if not version_row:
        return None
    return str(version_row["value"])


def _rebuild_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = OFF;
        DROP TABLE IF EXISTS app_meta;
        DROP TABLE IF EXISTS string_memberships;
        DROP TABLE IF EXISTS string_remarks;
        DROP TABLE IF EXISTS string_translations;
        DROP TABLE IF EXISTS strings;
        DROP TABLE IF EXISTS dev_versions;
        DROP TABLE IF EXISTS project_schemas;
        DROP TABLE IF EXISTS projects;
        DROP TABLE IF EXISTS import_rows;
        DROP TABLE IF EXISTS imports;
        DROP TABLE IF EXISTS jobs;

        DROP TABLE IF EXISTS branch_heads;
        DROP TABLE IF EXISTS snapshot_items;
        DROP TABLE IF EXISTS snapshots;
        DROP TABLE IF EXISTS translations;
        DROP TABLE IF EXISTS entries;
        PRAGMA foreign_keys = ON;
        """
    )
    conn.executescript(
        """
        CREATE TABLE app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE projects (
            project_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE project_schemas (
            schema_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            fixed_columns_json TEXT NOT NULL,
            translation_columns_json TEXT NOT NULL,
            remark_columns_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE strings (
            string_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            business_key TEXT NOT NULL,
            file_name TEXT,
            source TEXT NOT NULL,
            deleted_at TEXT,
            trash_until TEXT,
            restored_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(project_id, business_key),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE INDEX idx_strings_project_key ON strings(project_id, business_key);
        CREATE INDEX idx_strings_deleted_at ON strings(project_id, deleted_at);

        CREATE TABLE string_translations (
            string_id INTEGER NOT NULL,
            lang TEXT NOT NULL,
            target_text TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (string_id, lang),
            FOREIGN KEY (string_id) REFERENCES strings(string_id) ON DELETE CASCADE
        );

        CREATE TABLE string_remarks (
            string_id INTEGER NOT NULL,
            remark_key TEXT NOT NULL,
            remark_value TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (string_id, remark_key),
            FOREIGN KEY (string_id) REFERENCES strings(string_id) ON DELETE CASCADE
        );

        CREATE TABLE dev_versions (
            project_id INTEGER NOT NULL,
            version TEXT NOT NULL,
            version_line TEXT NOT NULL,
            is_candidate_release INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            promoted_at TEXT,
            PRIMARY KEY (project_id, version),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE string_memberships (
            string_id INTEGER NOT NULL,
            membership_type TEXT NOT NULL CHECK (membership_type IN ('rel', 'dev')),
            membership_value TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (string_id, membership_type, membership_value),
            FOREIGN KEY (string_id) REFERENCES strings(string_id) ON DELETE CASCADE
        );

        CREATE INDEX idx_memberships_type_value
        ON string_memberships(membership_type, membership_value);

        CREATE TABLE imports (
            import_batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            meta_json TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE import_rows (
            import_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_batch_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            sheet_name TEXT NOT NULL,
            row_index INTEGER NOT NULL,
            business_key TEXT,
            source TEXT,
            status TEXT NOT NULL,
            message TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (import_batch_id) REFERENCES imports(import_batch_id) ON DELETE CASCADE
        );

        CREATE INDEX idx_import_rows_batch ON import_rows(import_batch_id);

        CREATE TABLE jobs (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            input_json TEXT NOT NULL DEFAULT '{}',
            summary_json TEXT NOT NULL DEFAULT '{}',
            report_path TEXT,
            artifact_path TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            finished_at TEXT
        );

        CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
        """
    )

    created_at = _now_iso()
    conn.execute(
        "INSERT INTO app_meta(key, value) VALUES ('schema_version', ?)",
        (SCHEMA_VERSION,),
    )
    conn.execute(
        """
        INSERT INTO projects(project_id, name, is_default, created_at)
        VALUES (1, 'Default Project', 1, ?)
        """,
        (created_at,),
    )
    conn.execute(
        """
        INSERT INTO project_schemas(
            project_id,
            fixed_columns_json,
            translation_columns_json,
            remark_columns_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            1,
            json.dumps(
                {
                    "file_name": "file_name",
                    "business_key": "business_key",
                    "source": "source",
                },
                ensure_ascii=False,
            ),
            json.dumps(["fr", "en"], ensure_ascii=False),
            json.dumps(["context"], ensure_ascii=False),
            created_at,
        ),
    )
    conn.commit()


@contextmanager
def get_conn(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def json_dumps(payload: dict[str, Any] | list[Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def json_loads(payload: str | None) -> Any:
    if not payload:
        return {}
    return json.loads(payload)
