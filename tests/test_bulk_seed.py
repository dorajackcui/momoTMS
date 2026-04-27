import subprocess
import sys

import pytest
import openpyxl
from app.db import init_db, get_conn
from app.services.variant.store import _VariantStore
from app.services.variant.bindings import _ScopeBindingStore
from app.services.shared.utils import now_iso
from app.services.bulk.excel_reader import read_excel_chunks, BulkSeedError
from app.services.bulk.writer import BulkVariantWriter
from app.services.project.service import ProjectService
from app.services.branch.models import BranchRef


def _create_project_and_entries(conn, n=3):
    conn.execute(
        "INSERT INTO projects(name, is_default, created_at) VALUES ('test', 1, '2026-01-01T00:00:00+00:00')"
    )
    conn.execute(
        """INSERT INTO project_schemas(project_id, fixed_columns_json, translation_columns_json,
           remark_columns_json, pivot_language, pivoted_languages_json, created_at)
           VALUES (1, '{"business_key":"Key","source":"MsgStr","file_name":"file_name"}',
           '["fr","en"]', '["context"]', NULL, '[]', '2026-01-01T00:00:00+00:00')"""
    )
    ts = "2026-01-01T00:00:00+00:00"
    for i in range(1, n + 1):
        conn.execute(
            "INSERT INTO entries(project_id, business_key, created_at, updated_at) VALUES (1, ?, ?, ?)",
            (f"key_{i}", ts, ts),
        )


def test_bulk_create_variants():
    init_db()
    store = _VariantStore()
    ts = now_iso()
    with get_conn() as conn:
        _create_project_and_entries(conn, n=3)
        rows = [
            (1, "file1.xlsx", "Hello", ts),
            (2, "file1.xlsx", "World", ts),
            (3, "file2.xlsx", "Foo", ts),
        ]
        variant_ids = store.bulk_create_variants(rows, conn=conn)
        assert len(variant_ids) == 3
        assert all(isinstance(vid, int) for vid in variant_ids)
        db_rows = conn.execute("SELECT * FROM variants ORDER BY variant_id").fetchall()
        assert len(db_rows) == 3
        assert db_rows[0]["entry_id"] == 1
        assert db_rows[0]["source"] == "Hello"
        assert db_rows[0]["pivot_status"] == "init"
        assert db_rows[0]["orphaned_at"] is None


def test_bulk_write_translations():
    init_db()
    store = _VariantStore()
    ts = now_iso()
    with get_conn() as conn:
        _create_project_and_entries(conn, n=2)
        variant_ids = store.bulk_create_variants(
            [(1, "f.xlsx", "Hello", ts), (2, "f.xlsx", "World", ts)],
            conn=conn,
        )
        translation_rows = [
            (variant_ids[0], "fr", "Bonjour", ts),
            (variant_ids[0], "en", "Hello", ts),
            (variant_ids[1], "fr", "Monde", ts),
            (variant_ids[1], "en", "World", ts),
        ]
        store.bulk_write_translations(translation_rows, conn=conn)
        db_rows = conn.execute(
            "SELECT * FROM variant_translations ORDER BY variant_id, lang"
        ).fetchall()
        assert len(db_rows) == 4
        assert db_rows[0]["lang"] == "en"
        assert db_rows[0]["target_text"] == "Hello"


def test_bulk_write_remarks():
    init_db()
    store = _VariantStore()
    ts = now_iso()
    with get_conn() as conn:
        _create_project_and_entries(conn, n=1)
        variant_ids = store.bulk_create_variants(
            [(1, "f.xlsx", "Hello", ts)],
            conn=conn,
        )
        remark_rows = [(variant_ids[0], "context", "greeting", ts)]
        store.bulk_write_remarks(remark_rows, conn=conn)
        db_rows = conn.execute("SELECT * FROM variant_remarks").fetchall()
        assert len(db_rows) == 1
        assert db_rows[0]["remark_key"] == "context"
        assert db_rows[0]["remark_value"] == "greeting"


def test_bulk_bind():
    init_db()
    store = _VariantStore()
    binding_store = _ScopeBindingStore()
    ts = now_iso()
    with get_conn() as conn:
        _create_project_and_entries(conn, n=3)
        variant_ids = store.bulk_create_variants(
            [
                (1, "f.xlsx", "Hello", ts),
                (2, "f.xlsx", "World", ts),
                (3, "f.xlsx", "Foo", ts),
            ],
            conn=conn,
        )
        binding_rows = [
            ("rel", "current", 1, variant_ids[0], ts),
            ("rel", "current", 2, variant_ids[1], ts),
            ("rel", "current", 3, variant_ids[2], ts),
        ]
        binding_store.bulk_bind(binding_rows, conn=conn)
        db_rows = conn.execute(
            "SELECT * FROM scope_bindings ORDER BY entry_id"
        ).fetchall()
        assert len(db_rows) == 3
        assert db_rows[0]["scope_type"] == "rel"
        assert db_rows[0]["scope_value"] == "current"
        assert db_rows[0]["variant_id"] == variant_ids[0]


def _create_test_workbook(path, headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)


def test_read_excel_chunks_basic(tmp_path):
    workbook_path = tmp_path / "test.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[
            ["key_1", "Hello", "Bonjour", "Hello", "greeting"],
            ["key_2", "World", "Monde", "World", "noun"],
            ["key_3", "Foo", "Fou", "Foo", "test"],
        ],
    )
    schema = {
        "fixed_columns": {"business_key": "Key", "source": "MsgStr", "file_name": "file_name"},
        "translation_columns": ["fr", "en"],
        "remark_columns": ["context"],
    }
    chunks = list(read_excel_chunks(str(workbook_path), schema, chunk_size=2))
    assert len(chunks) == 2
    assert len(chunks[0]) == 2
    assert len(chunks[1]) == 1
    first_row = chunks[0][0]
    assert first_row["business_key"] == "key_1"
    assert first_row["source"] == "Hello"
    assert first_row["translations"] == {"fr": "Bonjour", "en": "Hello"}
    assert first_row["remarks"] == {"context": "greeting"}
    assert first_row["file_name"] == "test.xlsx"
    assert first_row["sheet_name"] == "Sheet1"


def test_read_excel_chunks_fails_on_missing_header(tmp_path):
    workbook_path = tmp_path / "bad.xlsx"
    _create_test_workbook(workbook_path, headers=["Key", "wrong_col"], rows=[["k1", "v1"]])
    schema = {
        "fixed_columns": {"business_key": "Key", "source": "MsgStr", "file_name": "file_name"},
        "translation_columns": ["fr"],
        "remark_columns": [],
    }
    with pytest.raises(BulkSeedError, match="missing required header: MsgStr"):
        list(read_excel_chunks(str(workbook_path), schema))


def test_read_excel_chunks_fails_on_blank_business_key(tmp_path):
    workbook_path = tmp_path / "blank.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr"],
        rows=[["", "Hello", "Bonjour"]],
    )
    schema = {
        "fixed_columns": {"business_key": "Key", "source": "MsgStr", "file_name": "file_name"},
        "translation_columns": ["fr"],
        "remark_columns": [],
    }
    with pytest.raises(BulkSeedError, match="blank business_key"):
        list(read_excel_chunks(str(workbook_path), schema))


def _create_project_with_schema():
    init_db()
    service = ProjectService()
    project = service.create_project(
        "Test Project",
        ["fr", "en"],
        ["context"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    return int(project["project_id"])


def test_bulk_writer_seed_rel_current(tmp_path):
    project_id = _create_project_with_schema()
    workbook_path = tmp_path / "data.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[
            ["key_1", "Hello", "Bonjour", "Hello", "greeting"],
            ["key_2", "World", "Monde", "World", "noun"],
            ["key_3", "Foo", "Fou", "Foo", "test"],
        ],
    )
    writer = BulkVariantWriter()
    result = writer.seed(
        project_id=project_id,
        branch_ref=BranchRef.rel_current(),
        workbook_path=str(workbook_path),
        chunk_size=2,
    )
    assert result["entries_created"] == 3
    assert result["variants_created"] == 3
    assert result["bindings_created"] == 3
    with get_conn() as conn:
        entries = conn.execute("SELECT * FROM entries WHERE project_id = ?", (project_id,)).fetchall()
        assert len(entries) == 3
        variants = conn.execute("SELECT * FROM variants").fetchall()
        assert len(variants) == 3
        assert all(v["pivot_status"] == "init" for v in variants)
        assert all(v["orphaned_at"] is None for v in variants)
        translations = conn.execute("SELECT * FROM variant_translations").fetchall()
        assert len(translations) == 6  # 3 variants * 2 languages
        remarks = conn.execute("SELECT * FROM variant_remarks").fetchall()
        assert len(remarks) == 3  # 3 variants * 1 remark column
        bindings = conn.execute("SELECT * FROM scope_bindings").fetchall()
        assert len(bindings) == 3
        assert all(b["scope_type"] == "rel" and b["scope_value"] == "current" for b in bindings)


def test_bulk_writer_seed_dev_branch(tmp_path):
    project_id = _create_project_with_schema()
    workbook_path = tmp_path / "data.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[["key_1", "Hello", "Bonjour", "Hello", "greeting"]],
    )
    writer = BulkVariantWriter()
    result = writer.seed(
        project_id=project_id,
        branch_ref=BranchRef.dev("2.4.1"),
        workbook_path=str(workbook_path),
    )
    assert result["variants_created"] == 1
    with get_conn() as conn:
        bindings = conn.execute("SELECT * FROM scope_bindings").fetchall()
        assert bindings[0]["scope_type"] == "dev"
        assert bindings[0]["scope_value"] == "2.4.1"
        dev_row = conn.execute(
            "SELECT * FROM dev_versions WHERE version = '2.4.1'"
        ).fetchone()
        assert dev_row["bootstrapped_at"] is not None


def test_bulk_writer_rejects_nonempty_project(tmp_path):
    project_id = _create_project_with_schema()
    workbook_path = tmp_path / "data.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[["key_1", "Hello", "Bonjour", "Hello", "greeting"]],
    )
    writer = BulkVariantWriter()
    writer.seed(
        project_id=project_id,
        branch_ref=BranchRef.rel_current(),
        workbook_path=str(workbook_path),
    )
    workbook_path2 = tmp_path / "data2.xlsx"
    _create_test_workbook(
        workbook_path2,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[["key_2", "World", "Monde", "World", "noun"]],
    )
    with pytest.raises(ValueError, match="already has variant data"):
        writer.seed(
            project_id=project_id,
            branch_ref=BranchRef.rel_current(),
            workbook_path=str(workbook_path2),
        )


def test_cli_missing_args():
    result = subprocess.run(
        [sys.executable, "scripts/seed_variants.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "required" in result.stderr.lower() or "error" in result.stderr.lower()


def test_cli_end_to_end(tmp_path, monkeypatch):
    db_path = tmp_path / "data" / "tms.db"
    monkeypatch.setenv("MOMO_TMS_DB_PATH", str(db_path))
    workbook_path = tmp_path / "data.xlsx"
    _create_test_workbook(
        workbook_path,
        headers=["Key", "MsgStr", "fr", "en", "context"],
        rows=[
            ["key_1", "Hello", "Bonjour", "Hello", "greeting"],
            ["key_2", "World", "Monde", "World", "noun"],
        ],
    )
    init_db()
    service = ProjectService()
    project = service.create_project(
        "CLI Test",
        ["fr", "en"],
        ["context"],
        business_key_header="Key",
        source_header="MsgStr",
    )
    project_id = int(project["project_id"])

    result = subprocess.run(
        [
            sys.executable, "scripts/seed_variants.py",
            "--project-id", str(project_id),
            "--branch", "rel/current",
            "--workbook", str(workbook_path),
        ],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "MOMO_TMS_DB_PATH": str(db_path)},
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "entries created:  2" in result.stdout
    assert "variants created: 2" in result.stdout
    assert "bindings created: 2" in result.stdout
