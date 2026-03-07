from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app


def _upload_folder(client: TestClient, url: str, root: Path, extra_fields: list[tuple[str, str]] | None = None):
    files = []
    for file_path in sorted(root.rglob("*.xlsx")):
        files.append(
            (
                "files",
                (
                    file_path.name,
                    file_path.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )
        )
        files.append(
            (
                "relative_paths",
                (
                    None,
                    str(file_path.relative_to(root)).replace("\\", "/"),
                ),
            )
        )
    if extra_fields:
        for key, value in extra_fields:
            files.append((key, (None, value)))
    return client.post(url, files=files)


def _write_workbook(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_variant_read_models_and_upload_endpoints() -> None:
    with TestClient(app) as client:
        reset_response = client.post("/api/demo/reset")
        assert reset_response.status_code == 200

        projects_response = client.get("/api/projects")
        assert projects_response.status_code == 200
        projects_payload = projects_response.json()
        assert len(projects_payload) == 1
        project_id = projects_payload[0]["project_id"]

        sample_root = Path("data/demo_samples/core-cycle")
        import_response = _upload_folder(
            client,
            f"/api/projects/{project_id}/imports/upload-folder",
            sample_root / "import_bundle",
        )
        assert import_response.status_code == 200
        import_job = import_response.json()
        batch_id = import_job["job"]["summary"]["import_batch_id"]

        dev_import_response = client.post(
            f"/api/projects/{project_id}/dev-versions/import",
            json={
                "import_batch_id": batch_id,
                "version": "2.2.3",
                "mark_as_candidate": True,
            },
        )
        assert dev_import_response.status_code == 200

        summary_response = client.get(f"/api/projects/{project_id}/scopes/summary", params={"lang": "fr"})
        assert summary_response.status_code == 200
        scope_values = {
            f"{row['scope_type']}/{row['scope_value']}"
            for row in summary_response.json()["scopes"]
        }
        assert "rel/current" in scope_values
        assert "dev/2.2.3" in scope_values

        compare_response = client.get(
            f"/api/projects/{project_id}/scopes/compare",
            params={
                "base": "rel/current",
                "target": "dev/2.2.3",
                "lang": "fr",
            },
        )
        assert compare_response.status_code == 200
        compare_payload = compare_response.json()
        compare_rows = {row["business_key"]: row for row in compare_payload["rows"]}
        assert compare_rows["rel.locked.same"]["state"] == "diverged"
        assert "file_name_changed" in compare_rows["rel.locked.same"]["diff_categories"]
        assert compare_rows["rel.locked.changed"]["state"] == "diverged"
        assert "source_changed" in compare_rows["rel.locked.changed"]["diff_categories"]
        assert compare_rows["dev.new.entry"]["state"] == "target_only"
        assert compare_rows["common.welcome"]["state"] == "base_only"

        second_dev_import_response = client.post(
            f"/api/projects/{project_id}/dev-versions/import",
            json={
                "import_batch_id": batch_id,
                "version": "2.2.4",
                "mark_as_candidate": False,
            },
        )
        assert second_dev_import_response.status_code == 200

        dev_to_dev_compare = client.get(
            f"/api/projects/{project_id}/scopes/compare",
            params={
                "base": "dev/2.2.3",
                "target": "dev/2.2.4",
                "lang": "fr",
            },
        )
        assert dev_to_dev_compare.status_code == 200
        assert all(row["state"] == "aligned" for row in dev_to_dev_compare.json()["rows"])

        entry_response = client.get(f"/api/projects/{project_id}/master/entries/rel.locked.same")
        assert entry_response.status_code == 200
        entry_payload = entry_response.json()
        assert len(entry_payload["results"]) == 3

        source_response = client.get(
            f"/api/projects/{project_id}/master/search",
            params={"source": "New source from dev"},
        )
        assert source_response.status_code == 200
        search_payload = source_response.json()
        assert any(row["business_key"] == "dev.new.entry" for row in search_payload["results"])

        paged_compare = client.get(
            f"/api/projects/{project_id}/scopes/compare",
            params={
                "base": "rel/current",
                "target": "dev/2.2.3",
                "lang": "fr",
                "page": 1,
                "page_size": 2,
                "state": "diverged",
            },
        )
        assert paged_compare.status_code == 200
        paged_payload = paged_compare.json()
        assert paged_payload["total_rows"] >= 2
        assert len(paged_payload["rows"]) == 2
        assert all(row["state"] == "diverged" for row in paged_payload["rows"])

        queue_response = client.get(
            f"/api/projects/{project_id}/translation-queue",
            params={
                "target": "dev/2.2.3",
                "lang": "fr",
                "page": 1,
                "page_size": 3,
                "priority_status": "needs_translation",
            },
        )
        assert queue_response.status_code == 200
        queue_payload = queue_response.json()
        assert queue_payload["target_scope"] == "dev/2.2.3"
        assert queue_payload["page_size"] == 3
        assert all(row["priority_status"] == "needs_translation" for row in queue_payload["rows"])

        fill_response = _upload_folder(
            client,
            f"/api/projects/{project_id}/fill/upload-folder",
            sample_root / "fill_source",
            extra_fields=[("lang", "fr")],
        )
        assert fill_response.status_code == 200
        assert fill_response.json()["job"]["job_type"] == "fill_upload_folder"

        qa_response = _upload_folder(
            client,
            f"/api/projects/{project_id}/qa/upload-folder",
            sample_root / "fill_source",
            extra_fields=[("lang", "fr")],
        )
        assert qa_response.status_code == 200
        assert qa_response.json()["job"]["job_type"] == "qa_upload_folder"


def test_create_project_and_isolate_content() -> None:
    with TestClient(app) as client:
        reset_response = client.post("/api/demo/reset")
        assert reset_response.status_code == 200

        create_response = client.post(
            "/api/projects",
            json={
                "name": "Second Project",
                "translation_columns": ["fr", "en", "de"],
                "remark_columns": ["context", "speaker"],
            },
        )
        assert create_response.status_code == 200
        project_id = create_response.json()["project_id"]

        state_response = client.get(f"/api/projects/{project_id}/state")
        assert state_response.status_code == 200
        state_payload = state_response.json()
        assert state_payload["project"]["name"] == "Second Project"
        assert state_payload["schema"]["translation_columns"] == ["fr", "en", "de"]
        assert state_payload["schema"]["remark_columns"] == ["context", "speaker"]
        assert state_payload["dev_versions"] == []


def test_product_app_route_serves_built_shell() -> None:
    with TestClient(app) as client:
        response = client.get("/app")
        assert response.status_code == 200
        assert "Momo TMS Product App" in response.text


def test_upload_folder_rejects_non_xlsx_files(tmp_path) -> None:
    bad_file = tmp_path / "bad" / "bad.txt"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_text("bad", encoding="utf-8")

    with TestClient(app) as client:
        response = client.post(
            "/api/imports/upload-folder",
            files=[
                (
                    "files",
                    (
                        "bad.txt",
                        bad_file.read_bytes(),
                        "text/plain",
                    ),
                ),
                ("relative_paths", (None, "bad.txt")),
            ],
        )
    assert response.status_code == 400
    assert "unsupported upload file" in response.json()["detail"]


def test_import_upload_preview_and_custom_column_mapping(tmp_path) -> None:
    root = tmp_path / "custom-import"
    workbook_path = root / "nested" / "custom.xlsx"
    _write_workbook(
        workbook_path,
        [
            ["bundle_name", "key_id", "jp_source", "fr_text", "en_text", "memo"],
            [" ui ", "screen.title", "原文", "Bonjour", "Hello", "home"],
        ],
    )

    with TestClient(app) as client:
        reset_response = client.post("/api/demo/reset")
        assert reset_response.status_code == 200

        projects_response = client.get("/api/projects")
        project_id = projects_response.json()[0]["project_id"]

        preview_response = _upload_folder(
            client,
            "/api/imports/upload-folder/preview",
            root,
        )
        assert preview_response.status_code == 200
        preview_payload = preview_response.json()
        assert preview_payload["file_count"] == 1
        assert preview_payload["sheet_count"] == 1
        sheet_preview = preview_payload["sheet_previews"][0]
        assert sheet_preview["derived_file_name"] == "nested/custom.xlsx"
        assert sheet_preview["auto_match_ready"] is False
        assert "business_key" in sheet_preview["missing_targets"]
        assert "source" in sheet_preview["missing_targets"]
        assert "translation:fr" in sheet_preview["missing_targets"]
        assert "remark:context" in sheet_preview["missing_targets"]

        mapping = {
            sheet_preview["sheet_key"]: {
                "business_key": "key_id",
                "source": "jp_source",
                "translation_columns": {
                    "fr": "fr_text",
                    "en": "en_text",
                },
                "remark_columns": {
                    "context": "memo",
                },
            }
        }
        import_response = _upload_folder(
            client,
            "/api/imports/upload-folder",
            root,
            extra_fields=[("column_mapping_json", json.dumps(mapping))],
        )
        assert import_response.status_code == 200
        import_job = import_response.json()
        batch_id = import_job["job"]["summary"]["import_batch_id"]

        report_response = client.get(f"/api/imports/{batch_id}/report")
        assert report_response.status_code == 200
        report_payload = report_response.json()
        ok_rows = [row for row in report_payload["rows"] if row["status"] == "ok"]
        assert len(ok_rows) == 1
        assert ok_rows[0]["business_key"] == "screen.title"
        assert ok_rows[0]["source"] == "原文"
        assert ok_rows[0]["payload"]["file_name"] == "nested/custom.xlsx"

        product_preview_response = _upload_folder(
            client,
            f"/api/projects/{project_id}/imports/upload-folder/preview",
            root,
        )
        assert product_preview_response.status_code == 200
        product_preview_payload = product_preview_response.json()
        assert product_preview_payload["sheet_previews"][0]["missing_targets"]
        assert ok_rows[0]["payload"]["translations"]["fr"] == "Bonjour"
        assert ok_rows[0]["payload"]["remarks"]["context"] == "home"

        project_import_response = _upload_folder(
            client,
            f"/api/projects/{project_id}/imports/upload-folder",
            root,
            extra_fields=[("column_mapping_json", json.dumps(mapping))],
        )
        assert project_import_response.status_code == 200
        project_batch_id = project_import_response.json()["job"]["summary"]["import_batch_id"]

        project_report_response = client.get(f"/api/projects/{project_id}/imports/{project_batch_id}/report")
        assert project_report_response.status_code == 200
        project_ok_rows = [row for row in project_report_response.json()["rows"] if row["status"] == "ok"]
        assert len(project_ok_rows) == 1
        assert project_ok_rows[0]["business_key"] == "screen.title"


def test_import_upload_uses_workbook_relative_path_as_file_name(tmp_path) -> None:
    root = tmp_path / "custom-import-no-file-name"
    workbook_path = root / "nested" / "custom.xlsx"
    _write_workbook(
        workbook_path,
        [
            ["Key", "Source", "fr", "en", "LineDescription"],
            ["screen.title", "原文", "Bonjour", "Hello", "home"],
        ],
    )

    with TestClient(app) as client:
        reset_response = client.post("/api/demo/reset")
        assert reset_response.status_code == 200

        preview_response = _upload_folder(
            client,
            "/api/imports/upload-folder/preview",
            root,
        )
        assert preview_response.status_code == 200
        sheet_preview = preview_response.json()["sheet_previews"][0]

        mapping = {
            sheet_preview["sheet_key"]: {
                "business_key": "Key",
                "source": "Source",
                "translation_columns": {
                    "fr": "fr",
                    "en": "en",
                },
                "remark_columns": {
                    "context": "LineDescription",
                },
            }
        }
        import_response = _upload_folder(
            client,
            "/api/imports/upload-folder",
            root,
            extra_fields=[("column_mapping_json", json.dumps(mapping))],
        )
        assert import_response.status_code == 200
        batch_id = import_response.json()["job"]["summary"]["import_batch_id"]

        report_response = client.get(f"/api/imports/{batch_id}/report")
        assert report_response.status_code == 200
        report_payload = report_response.json()
        ok_rows = [row for row in report_payload["rows"] if row["status"] == "ok"]
        assert len(ok_rows) == 1
        assert ok_rows[0]["payload"]["file_name"] == "nested/custom.xlsx"


def test_invalid_scope_refs_return_400_in_read_model_routes() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        responses = [
            client.get("/api/scopes/compare", params={"base": "bad", "target": "dev/1.0.0"}),
            client.get(
                "/api/projects/1/scopes/compare",
                params={"base": "rel/current", "target": "bad"},
            ),
            client.get("/api/translation-queue", params={"target": "bad"}),
            client.get("/api/projects/1/translation-queue", params={"target": "bad"}),
        ]

    for response in responses:
        assert response.status_code == 400
        assert "invalid scope ref" in response.json()["detail"]
