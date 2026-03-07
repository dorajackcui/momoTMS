from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path("data/tms.db")
SCHEMA_VERSION = "variant-v3"


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
        DROP TABLE IF EXISTS scope_bindings;
        DROP TABLE IF EXISTS retained_variants;
        DROP TABLE IF EXISTS variant_remarks;
        DROP TABLE IF EXISTS variant_translations;
        DROP TABLE IF EXISTS variants;
        DROP TABLE IF EXISTS entries;
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
        DROP TABLE IF EXISTS strings;
        DROP TABLE IF EXISTS string_memberships;
        DROP TABLE IF EXISTS string_remarks;
        DROP TABLE IF EXISTS string_translations;
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
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX idx_projects_name ON projects(name);

        CREATE TABLE project_schemas (
            schema_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            fixed_columns_json TEXT NOT NULL,
            translation_columns_json TEXT NOT NULL,
            remark_columns_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE TABLE entries (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            business_key TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(project_id, business_key),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE INDEX idx_entries_project_key ON entries(project_id, business_key);

        CREATE TABLE variants (
            variant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            file_name TEXT,
            source TEXT NOT NULL,
            orphaned_at TEXT,
            trashed_at TEXT,
            trash_until TEXT,
            restored_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (entry_id) REFERENCES entries(entry_id) ON DELETE CASCADE
        );

        CREATE INDEX idx_variants_entry ON variants(entry_id);
        CREATE INDEX idx_variants_trashed ON variants(trashed_at);
        CREATE INDEX idx_variants_orphaned ON variants(orphaned_at);

        CREATE TABLE variant_translations (
            variant_id INTEGER NOT NULL,
            lang TEXT NOT NULL,
            target_text TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (variant_id, lang),
            FOREIGN KEY (variant_id) REFERENCES variants(variant_id) ON DELETE CASCADE
        );

        CREATE TABLE variant_remarks (
            variant_id INTEGER NOT NULL,
            remark_key TEXT NOT NULL,
            remark_value TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (variant_id, remark_key),
            FOREIGN KEY (variant_id) REFERENCES variants(variant_id) ON DELETE CASCADE
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

        CREATE TABLE scope_bindings (
            scope_type TEXT NOT NULL CHECK (scope_type IN ('rel', 'dev')),
            scope_value TEXT NOT NULL,
            entry_id INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (scope_type, scope_value, entry_id),
            FOREIGN KEY (entry_id) REFERENCES entries(entry_id) ON DELETE CASCADE,
            FOREIGN KEY (variant_id) REFERENCES variants(variant_id) ON DELETE CASCADE
        );

        CREATE INDEX idx_scope_bindings_scope
        ON scope_bindings(scope_type, scope_value);
        CREATE INDEX idx_scope_bindings_variant
        ON scope_bindings(variant_id);

        CREATE TABLE retained_variants (
            variant_id INTEGER PRIMARY KEY,
            entry_id INTEGER NOT NULL,
            last_active_scope_type TEXT NOT NULL,
            last_active_scope_value TEXT NOT NULL,
            retained_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (entry_id) REFERENCES entries(entry_id) ON DELETE CASCADE,
            FOREIGN KEY (variant_id) REFERENCES variants(variant_id) ON DELETE CASCADE
        );

        CREATE INDEX idx_retained_variants_entry ON retained_variants(entry_id);

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
            project_id INTEGER NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            input_json TEXT NOT NULL DEFAULT '{}',
            summary_json TEXT NOT NULL DEFAULT '{}',
            report_path TEXT,
            artifact_path TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            finished_at TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );

        CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
        CREATE INDEX idx_jobs_project_created_at ON jobs(project_id, job_id DESC);
        """
    )

    conn.execute(
        "INSERT INTO app_meta(key, value) VALUES ('schema_version', ?)",
        (SCHEMA_VERSION,),
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
