from pathlib import Path

from app.db import DB_PATH, get_conn, json_dumps
from app.services.demo.service import DemoService
from app.services.shared.utils import now_iso
from app.services.variant.compatibility import StringService
from app.services.variant.facade import VariantService
from app.services.workflows.dev_versions import DevVersionService


def reset_demo() -> None:
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
    DemoService().reset()


def make_import_batch(rows: list[dict]) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO imports(project_id, created_at, meta_json)
            VALUES (?, ?, ?)
            """,
            (1, now_iso(), json_dumps({"source": "unit-test"})),
        )
        batch_id = int(cur.lastrowid)
        for index, payload in enumerate(rows, start=2):
            conn.execute(
                """
                INSERT INTO import_rows(
                    import_batch_id,
                    file_path,
                    sheet_name,
                    row_index,
                    business_key,
                    source,
                    status,
                    message,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, 'ok', NULL, ?)
                """,
                (
                    batch_id,
                    "bundle.xlsx",
                    "Sheet1",
                    index,
                    payload["business_key"],
                    payload["source"],
                    json_dumps(payload),
                ),
            )
    return batch_id


def test_dev_import_covers_reuse_update_rebind_and_noop_paths() -> None:
    reset_demo()
    strings = StringService()
    variants = VariantService()

    reused_rel_id = strings.create_string("status.reused.rel", None, "Release source", {"fr": "Rel"}, {})
    strings.ensure_membership(reused_rel_id, "rel", "current")

    updated_dev_id = strings.create_string("status.updated.dev", None, "Old dev source", {"fr": "Old"}, {})
    strings.ensure_membership(updated_dev_id, "dev", "1.2.3")

    rebound_shared_id = strings.create_string("status.rebound.shared", None, "Shared source", {"fr": "Shared"}, {})
    strings.ensure_membership(rebound_shared_id, "rel", "current")
    strings.ensure_membership(rebound_shared_id, "dev", "1.2.3")

    noop_dev_id = strings.create_string("status.noop.dev", None, "Noop source", {"fr": "Noop"}, {})
    strings.ensure_membership(noop_dev_id, "dev", "1.2.3")

    entry = variants.get_or_create_entry("status.bound.existing")
    rel_variant_id = strings.create_string("status.bound.existing", None, "Rel source", {"fr": "Rel"}, {})
    strings.ensure_membership(rel_variant_id, "rel", "current")
    retained_variant_id = variants.create_variant(
        int(entry["entry_id"]),
        None,
        "Retained source",
        {"fr": "Keep"},
        {},
    )
    variants._retain_variant_if_inactive(retained_variant_id, int(entry["entry_id"]), "dev", "1.1.0")
    variants._refresh_orphan_states(int(entry["entry_id"]))

    batch_id = make_import_batch(
        [
            {
                "business_key": "status.created.new",
                "file_name": "created.xlsx",
                "source": "Created source",
                "translations": {"fr": "Created"},
                "remarks": {},
            },
            {
                "business_key": "status.reused.rel",
                "file_name": "",
                "source": "Release source",
                "translations": {"fr": "Rel"},
                "remarks": {},
            },
            {
                "business_key": "status.updated.dev",
                "file_name": "",
                "source": "Updated dev source",
                "translations": {"fr": "Updated"},
                "remarks": {},
            },
            {
                "business_key": "status.rebound.shared",
                "file_name": "",
                "source": "Changed shared source",
                "translations": {"fr": "Changed"},
                "remarks": {},
            },
            {
                "business_key": "status.bound.existing",
                "file_name": "",
                "source": "Retained source",
                "translations": {"fr": "Keep"},
                "remarks": {},
            },
            {
                "business_key": "status.noop.dev",
                "file_name": "",
                "source": "Noop source",
                "translations": {"fr": "Noop"},
                "remarks": {},
            },
        ]
    )

    result = DevVersionService().import_batch(batch_id, "1.2.3")
    statuses = {row["business_key"]: row["status"] for row in result["report_rows"]}

    assert statuses == {
        "status.created.new": "CREATED_VARIANT",
        "status.reused.rel": "REUSED_REL_VARIANT",
        "status.updated.dev": "UPDATED_BOUND_VARIANT",
        "status.rebound.shared": "REBOUND_FROM_REL_VARIANT",
        "status.bound.existing": "BOUND_EXISTING_VARIANT",
        "status.noop.dev": "NOOP_ALREADY_MATCHED",
    }
    assert result["summary"]["created_entry_count"] == 1
    assert result["summary"]["created_variant_count"] == 2
    assert result["summary"]["updated_bound_variant_count"] == 1
    assert result["summary"]["reused_rel_variant_count"] == 1
    assert result["summary"]["rebound_variant_count"] == 2
    assert result["summary"]["noop_count"] == 1
    assert result["summary"]["processed_count"] == 6
