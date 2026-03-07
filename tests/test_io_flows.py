from pathlib import Path

from openpyxl import Workbook, load_workbook

from app.db import DB_PATH, get_conn, init_db
from app.services.imports.service import ImportService
from app.services.project.service import ProjectService
from app.services.variant.compatibility import StringService
from app.services.workflows.fill import FillService
from app.services.workflows.qa import QaScanService


def reset_db() -> None:
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
    init_db()
    ProjectService().create_project("IO Test Project", ["fr", "en"], ["context"])


def write_workbook(file_path: Path, rows: list[list[object]]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    for row in rows:
        sheet.append(row)
    workbook.save(file_path)


def test_import_normalizes_fields_per_io_spec(tmp_path) -> None:
    reset_db()
    source_dir = tmp_path / "import"
    workbook_path = source_dir / "bundle.xlsx"
    write_workbook(
        workbook_path,
        [
            [" file_name ", " business_key ", " source ", " fr ", " en ", " context "],
            ["  ui/common.xlsx  ", "  spaced.key  ", "  Source text  ", "  Bonjour  ", "   ", "  mobile only  "],
            ["  bad.xlsx  ", "   ", "  Missing key source  ", "  Salut  ", "", "  ignored  "],
            ["  bad.xlsx  ", "  missing.source  ", "   ", "  No source  ", "", "  ignored  "],
        ],
    )

    summary = ImportService().import_directory(str(source_dir))
    report = ImportService().import_report(summary["import_batch_id"])

    assert summary["issues"] == 2
    rows = report["rows"]

    assert rows[0]["status"] == "ok"
    assert rows[0]["payload"] == {
        "file_name": "bundle.xlsx",
        "business_key": "spaced.key",
        "source": "Source text",
        "translations": {"fr": "  Bonjour  ", "en": ""},
        "remarks": {"context": "mobile only"},
    }

    assert rows[1]["status"] == "missing_business_key"
    assert rows[1]["business_key"] == ""
    assert rows[1]["payload"]["translations"]["fr"] == "  Salut  "

    assert rows[2]["status"] == "missing_source"
    assert rows[2]["source"] == ""
    assert rows[2]["payload"]["source"] == ""


def test_fill_uses_combined_key_and_skips_blank_content(tmp_path) -> None:
    reset_db()
    strings = StringService()

    rel_string_id = strings.create_string(
        business_key="fill.keep",
        file_name="release/fill.xlsx",
        source="Source keep",
        translations={"fr": "  Bonjour  ", "en": ""},
        remarks={"context": ""},
    )
    strings.ensure_membership(rel_string_id, "rel", "current")
    strings.create_string(
        business_key="fill.blank",
        file_name="release/fill.xlsx",
        source="Source blank",
        translations={"fr": "", "en": ""},
        remarks={"context": ""},
    )
    blank_id = strings.get_string("fill.blank", include_deleted=True)["string_id"]
    strings.ensure_membership(blank_id, "rel", "current")
    source_id = strings.create_string(
        business_key="fill.source",
        file_name="release/fill.xlsx",
        source="Canonical source",
        translations={"fr": "Mismatch target", "en": ""},
        remarks={"context": ""},
    )
    strings.ensure_membership(source_id, "rel", "current")

    source_dir = tmp_path / "fill_source"
    workbook_path = source_dir / "fill.xlsx"
    write_workbook(
        workbook_path,
        [
            ["file_name", "business_key", "source", "fr", "en", "context"],
            ["release/fill.xlsx", "fill.invalid", "   ", "", "", ""],
            ["release/fill.xlsx", "fill.missing", "Missing source", "", "", ""],
            ["release/fill.xlsx", "fill.source", "Source row changed", "", "", ""],
            ["release/fill.xlsx", "fill.blank", "Source blank", "   ", "", ""],
            ["release/fill.xlsx", "fill.keep", "Source keep", "   ", "", ""],
        ],
    )

    output_zip = tmp_path / "filled.zip"
    work_dir = tmp_path / "fill_output"
    result = FillService().fill_and_export(
        str(source_dir),
        str(output_zip),
        "fr",
        work_dir=str(work_dir),
    )

    assert result["filled_count"] == 1
    assert result["miss_key_count"] == 1
    assert result["src_mismatch_count"] == 1
    assert result["kept_original_count"] == 0
    assert result["skipped_invalid_combined_key_count"] == 1
    assert result["skipped_blank_content_count"] == 1

    statuses = {row["business_key"]: row["status"] for row in result["report_rows"]}
    assert statuses["fill.invalid"] == "SKIPPED_INVALID_COMBINED_KEY"
    assert statuses["fill.missing"] == "MISSING_KEY_IN_BASE"
    assert statuses["fill.source"] == "SRC_MISMATCH"
    assert statuses["fill.blank"] == "SKIPPED_BLANK_CONTENT"
    assert statuses["fill.keep"] == "FILLED"

    filled_workbook = load_workbook(work_dir / "fill.xlsx")
    sheet = filled_workbook.active
    assert sheet.cell(row=6, column=4).value == "  Bonjour  "
    assert sheet.cell(row=5, column=4).value == "   "


def test_qa_reads_translation_content_without_trimming(monkeypatch, tmp_path) -> None:
    reset_db()
    source_dir = tmp_path / "qa_source"
    workbook_path = source_dir / "qa.xlsx"
    write_workbook(
        workbook_path,
        [
            ["file_name", "business_key", "source", "fr", "en", "context"],
            ["qa/source.xlsx", "  qa.keep  ", "  Source text  ", "  Target text  ", "", ""],
        ],
    )

    captured: dict[str, str] = {}

    def fake_validate_pair(source: str, target: str):
        captured["source"] = source
        captured["target"] = target
        return []

    monkeypatch.setattr("app.services.workflows.qa.validate_pair", fake_validate_pair)

    result = QaScanService().scan_directory(str(source_dir), "fr")

    assert result["issue_count"] == 0
    assert captured["source"] == "Source text"
    assert captured["target"] == "  Target text  "


def test_string_service_normalizes_legacy_nulls_on_read() -> None:
    reset_db()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO entries(project_id, business_key, created_at, updated_at)
            VALUES (1, 'legacy.key', '2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00')
            """
        )
        entry_id = int(cur.lastrowid)
        cur = conn.execute(
            """
            INSERT INTO variants(entry_id, file_name, source, orphaned_at, created_at, updated_at)
            VALUES (?, NULL, 'Legacy source', '2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00')
            """,
            (entry_id,),
        )
        variant_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO variant_translations(variant_id, lang, target_text, updated_at)
            VALUES (?, 'fr', NULL, '2025-01-01T00:00:00+00:00')
            """,
            (variant_id,),
        )
        conn.execute(
            """
            INSERT INTO variant_remarks(variant_id, remark_key, remark_value, updated_at)
            VALUES (?, 'context', NULL, '2025-01-01T00:00:00+00:00')
            """,
            (variant_id,),
        )

    item = StringService().get_string("legacy.key", include_deleted=True)

    assert item is not None
    assert item["file_name"] == ""
    assert item["translations"]["fr"] == ""
    assert item["remarks"]["context"] == ""
