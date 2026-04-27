import pytest
from app.db import init_db, get_conn
from app.services.variant.store import _VariantStore
from app.services.variant.bindings import _ScopeBindingStore
from app.services.shared.utils import now_iso


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
