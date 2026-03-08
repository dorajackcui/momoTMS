from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path("data/tms.db")
DB_PATH_ENV_VAR = "MOMO_TMS_DB_PATH"
SCHEMA_VERSION = "variant-v4"
MODEL_SEMANTICS_KEY = "variant_model_semantics"
MODEL_SEMANTICS_VERSION = "canonical-source-v1"


def _dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_db_path(db_path: Path | str | None = None) -> Path:
    if db_path is not None:
        return Path(db_path)
    override = os.getenv(DB_PATH_ENV_VAR)
    if override:
        return Path(override)
    return DB_PATH


def init_db(db_path: Path | str | None = None) -> None:
    db_path = get_db_path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = _dict_factory
        conn.execute("PRAGMA foreign_keys = ON")
        if _current_schema_version(conn) != SCHEMA_VERSION:
            _rebuild_schema(conn)
        _apply_runtime_migrations(conn)
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


def _apply_runtime_migrations(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = ?",
        (MODEL_SEMANTICS_KEY,),
    ).fetchone()
    if row and str(row["value"]) == MODEL_SEMANTICS_VERSION:
        return

    entry_rows = conn.execute("SELECT entry_id FROM entries ORDER BY entry_id").fetchall()
    for entry_row in entry_rows:
        _collapse_entry_same_source_variants(conn, int(entry_row["entry_id"]))
        _refresh_entry_orphan_states(conn, int(entry_row["entry_id"]))

    conn.execute(
        """
        INSERT INTO app_meta(key, value)
        VALUES (?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
        """,
        (MODEL_SEMANTICS_KEY, MODEL_SEMANTICS_VERSION),
    )
    conn.commit()


def _collapse_entry_same_source_variants(conn: sqlite3.Connection, entry_id: int) -> None:
    variant_rows = conn.execute(
        """
        SELECT variant_id, source, orphaned_at, trashed_at, updated_at
        FROM variants
        WHERE entry_id = ?
        ORDER BY variant_id
        """,
        (entry_id,),
    ).fetchall()
    if len(variant_rows) < 2:
        return

    binding_rows = conn.execute(
        """
        SELECT variant_id, scope_type, scope_value
        FROM scope_bindings
        WHERE entry_id = ?
        ORDER BY scope_type, scope_value
        """,
        (entry_id,),
    ).fetchall()
    bindings_by_variant: dict[int, list[dict[str, Any]]] = {}
    for binding_row in binding_rows:
        bindings_by_variant.setdefault(int(binding_row["variant_id"]), []).append(binding_row)

    variants_by_source: dict[str, list[dict[str, Any]]] = {}
    for variant_row in variant_rows:
        variants_by_source.setdefault(str(variant_row["source"] or ""), []).append(variant_row)

    for variants in variants_by_source.values():
        if len(variants) < 2:
            continue
        canonical = max(
            variants,
            key=lambda item: _variant_model_rank(item, bindings_by_variant.get(int(item["variant_id"]), [])),
        )
        canonical_variant_id = int(canonical["variant_id"])
        duplicate_ids = [int(item["variant_id"]) for item in variants if int(item["variant_id"]) != canonical_variant_id]
        if not duplicate_ids:
            continue
        placeholders = ", ".join("?" for _ in duplicate_ids)
        conn.execute(
            f"""
            UPDATE scope_bindings
            SET variant_id = ?
            WHERE variant_id IN ({placeholders})
            """,
            [canonical_variant_id, *duplicate_ids],
        )
        conn.execute(
            f"DELETE FROM variants WHERE variant_id IN ({placeholders})",
            duplicate_ids,
        )


def _refresh_entry_orphan_states(conn: sqlite3.Connection, entry_id: int) -> None:
    variant_rows = conn.execute(
        """
        SELECT variant_id, orphaned_at, trashed_at
        FROM variants
        WHERE entry_id = ?
        ORDER BY variant_id
        """,
        (entry_id,),
    ).fetchall()
    binding_rows = conn.execute(
        """
        SELECT variant_id, COUNT(*) AS binding_count
        FROM scope_bindings
        WHERE entry_id = ?
        GROUP BY variant_id
        """,
        (entry_id,),
    ).fetchall()
    binding_counts = {int(row["variant_id"]): int(row["binding_count"] or 0) for row in binding_rows}
    timestamp = _now_iso()
    for variant_row in variant_rows:
        variant_id = int(variant_row["variant_id"])
        if variant_row["trashed_at"] is not None:
            orphaned_at = None
        elif binding_counts.get(variant_id, 0) == 0:
            orphaned_at = variant_row["orphaned_at"] or timestamp
        else:
            orphaned_at = None
        conn.execute(
            """
            UPDATE variants
            SET orphaned_at = ?
            WHERE variant_id = ?
            """,
            (orphaned_at, variant_id),
        )


def _variant_model_rank(
    variant_row: dict[str, Any],
    bindings: list[dict[str, Any]],
) -> tuple[int, int, int, int, str, int]:
    rel_bound = any(
        row["scope_type"] == "rel" and row["scope_value"] == "current"
        for row in bindings
    )
    active = bool(bindings)
    non_trashed = variant_row["trashed_at"] is None
    orphan_like = non_trashed and not active and variant_row["orphaned_at"] is not None
    return (
        1 if non_trashed else 0,
        1 if rel_bound else 0,
        1 if active else 0,
        1 if orphan_like else 0,
        str(variant_row["updated_at"] or ""),
        int(variant_row["variant_id"]),
    )


@contextmanager
def get_conn(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    db_path = get_db_path(db_path)
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
