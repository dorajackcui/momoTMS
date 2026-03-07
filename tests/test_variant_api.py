from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app
from app.services.demo.service import DemoService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.variant.services import EntryService, VariantCatalogService, VariantLifecycleService


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

        sample_root = Path(DemoService().sample_paths("core-cycle")["root"])
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
        assert '<div id="root"></div>' in response.text
        assert "/static/product-app/assets/" in response.text


def test_workbench_is_gone_and_variant_workbench_is_marked_internal() -> None:
    with TestClient(app) as client:
        workbench_response = client.get("/workbench")
        assert workbench_response.status_code == 410
        assert "workbench removed" in workbench_response.json()["detail"]

        variant_workbench_response = client.get("/variant-workbench")
        assert variant_workbench_response.status_code == 200
        assert "Deprecated internal validation page" in variant_workbench_response.text


def test_upload_folder_rejects_non_xlsx_files(tmp_path) -> None:
    bad_file = tmp_path / "bad" / "bad.txt"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_text("bad", encoding="utf-8")

    with TestClient(app) as client:
        reset_response = client.post("/api/demo/reset")
        assert reset_response.status_code == 200
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


def test_product_and_compat_bootstrap_surfaces_are_separated() -> None:
    with TestClient(app) as client:
        assert client.post("/api/demo/reset").status_code == 200

        compat_state = client.get("/api/state")
        assert compat_state.status_code == 200
        compat_payload = compat_state.json()
        assert "trash_count" in compat_payload
        assert "samples" in compat_payload

        product_state = client.get("/api/projects/1/state")
        assert product_state.status_code == 200
        product_payload = product_state.json()
        assert "trash_count" not in product_payload
        assert "samples" not in product_payload
        assert product_payload["project"]["project_id"] == 1
        assert product_payload["schema"]["translation_columns"] == ["fr", "en"]


def test_project_scoped_hotfix_and_trash_routes_replace_legacy_routes() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/api/demo/reset").status_code == 200

        legacy_responses = [
            client.post(
                "/api/rel/hotfix/active",
                json={"business_key": "common.welcome", "lang": "fr", "target_text": "Bonjour"},
            ),
            client.post(
                "/api/rel/hotfix/passive",
                json={"business_key": "hotfix.passive", "source": "Updated"},
            ),
            client.post("/api/trash/delete", json={"business_keys": ["common.welcome"]}),
            client.post("/api/trash/restore", json={"business_keys": ["common.welcome"]}),
        ]

        for response in legacy_responses:
            assert response.status_code == 404

        active_response = client.post(
            "/api/projects/1/scopes/rel/current/hotfix/active",
            json={
                "business_key": "common.welcome",
                "lang": "fr",
                "target_text": "  Bienvenue API  ",
            },
        )
        assert active_response.status_code == 200
        assert active_response.json()["job"]["job_type"] == "rel_hotfix_active"

        passive_response = client.post(
            "/api/projects/1/scopes/rel/current/hotfix/passive",
            json={
                "business_key": "hotfix.passive",
                "file_name": "release/common.xlsx",
                "source": "Passive source rewritten",
                "translations_by_lang": {"fr": "Passive fr", "en": "Passive en"},
                "remarks_by_key": {"context": "Passive context"},
            },
        )
        assert passive_response.status_code == 200
        assert passive_response.json()["job"]["job_type"] == "rel_hotfix_passive"

        active_string = client.get("/api/strings/common.welcome")
        assert active_string.status_code == 200
        assert active_string.json()["translations"]["fr"] == "  Bienvenue API  "

        delete_response = client.post(
            "/api/projects/1/variants/trash/delete",
            json={"scope_ref": "rel/current", "business_keys": ["common.welcome"]},
        )
        assert delete_response.status_code == 200
        delete_summary = delete_response.json()["job"]["summary"]
        assert delete_summary["trashed_variant_count"] == 1
        assert delete_summary["removed_scope_binding_count"] == 0

        deleted_string = client.get("/api/strings/common.welcome")
        assert deleted_string.status_code == 200
        deleted_payload = deleted_string.json()
        assert deleted_payload["deleted_at"] is not None

        restore_response = client.post(
            "/api/projects/1/variants/trash/restore",
            json={"variant_ids": [deleted_payload["string_id"]]},
        )
        assert restore_response.status_code == 200
        restore_summary = restore_response.json()["job"]["summary"]
        assert restore_summary["restored_count"] == 1

        restored_string = client.get("/api/strings/common.welcome")
        assert restored_string.status_code == 200
        restored_payload = restored_string.json()
        assert restored_payload["deleted_at"] is None
        assert restored_payload["memberships"] == []

        invalid_scope = client.post(
            "/api/projects/1/variants/trash/delete",
            json={"scope_ref": "rel/old", "business_keys": ["common.welcome"]},
        )
        assert invalid_scope.status_code == 400
        assert "invalid scope ref" in invalid_scope.json()["detail"]


def test_project_routes_enforce_import_and_job_ownership() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/api/demo/reset").status_code == 200
        create_response = client.post(
            "/api/projects",
            json={
                "name": "Second Project",
                "translation_columns": ["fr", "en"],
                "remark_columns": ["context"],
            },
        )
        assert create_response.status_code == 200
        second_project_id = create_response.json()["project_id"]

        sample_root = Path(DemoService().sample_paths("core-cycle")["root"])
        import_response = _upload_folder(
            client,
            f"/api/projects/{second_project_id}/imports/upload-folder",
            sample_root / "import_bundle",
        )
        assert import_response.status_code == 200
        second_batch_id = import_response.json()["job"]["summary"]["import_batch_id"]

        wrong_project_report = client.get(f"/api/projects/1/imports/{second_batch_id}/report")
        assert wrong_project_report.status_code == 404
        assert f"import batch not found: {second_batch_id}" in wrong_project_report.json()["detail"]

        wrong_project_import = client.post(
            "/api/projects/1/dev-versions/import",
            json={
                "import_batch_id": second_batch_id,
                "version": "2.2.3",
                "mark_as_candidate": True,
            },
        )
        assert wrong_project_import.status_code == 404
        assert f"import batch not found: {second_batch_id}" in wrong_project_import.json()["detail"]

        fill_response = client.post(
            f"/api/projects/{second_project_id}/fill",
            json={
                "source_dir": str(sample_root / "fill_source"),
                "lang": "fr",
            },
        )
        assert fill_response.status_code == 200
        fill_job = fill_response.json()["job"]
        artifact_name = Path(fill_job["artifact_path"]).name

        for path in [
            f"/api/projects/1/jobs/{fill_job['job_id']}",
            f"/api/projects/1/jobs/{fill_job['job_id']}/report",
            f"/api/projects/1/jobs/{fill_job['job_id']}/artifact/{artifact_name}",
        ]:
            response = client.get(path)
            assert response.status_code == 404
            assert f"job not found: {fill_job['job_id']}" in response.json()["detail"]


def test_inspection_routes_expose_variants_and_retained_entries() -> None:
    with TestClient(app) as client:
        assert client.post("/api/demo/reset").status_code == 200
        sample_root = Path(DemoService().sample_paths("core-cycle")["root"])

        import_response = _upload_folder(
            client,
            "/api/projects/1/imports/upload-folder",
            sample_root / "import_bundle",
        )
        assert import_response.status_code == 200
        batch_id = import_response.json()["job"]["summary"]["import_batch_id"]
        dev_import_response = client.post(
            "/api/projects/1/dev-versions/import",
            json={"import_batch_id": batch_id, "version": "2.2.3", "mark_as_candidate": True},
        )
        assert dev_import_response.status_code == 200
        promote_response = client.post("/api/projects/1/promote/execute", json={"version": "2.2.3"})
        assert promote_response.status_code == 200

        entry_variants = client.get("/api/projects/1/entries/common.welcome/variants")
        assert entry_variants.status_code == 200
        variants_payload = entry_variants.json()
        assert variants_payload["business_key"] == "common.welcome"
        assert variants_payload["variants"]
        assert any(variant["is_retained"] for variant in variants_payload["variants"])
        assert all("bindings" in variant for variant in variants_payload["variants"])

        retained_response = client.get("/api/projects/1/retained-variants")
        assert retained_response.status_code == 200
        retained_payload = retained_response.json()
        assert retained_payload["project_id"] == 1
        retained_keys = {row["business_key"] for row in retained_payload["results"]}
        assert "common.welcome" in retained_keys

        orphan_response = client.get("/api/projects/1/orphan-variants")
        assert orphan_response.status_code == 200
        assert orphan_response.json()["project_id"] == 1
        assert isinstance(orphan_response.json()["results"], list)


def test_inspection_routes_return_404_for_missing_or_cross_project_resources() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/api/demo/reset").status_code == 200
        create_response = client.post(
            "/api/projects",
            json={
                "name": "Inspection Project",
                "translation_columns": ["fr", "en"],
                "remark_columns": ["context"],
            },
        )
        assert create_response.status_code == 200
        second_project_id = create_response.json()["project_id"]

        missing_entry = client.get("/api/projects/1/entries/missing.key/variants")
        assert missing_entry.status_code == 404
        assert "entry not found" in missing_entry.json()["detail"]

        hidden_entry = client.get(f"/api/projects/{second_project_id}/entries/common.welcome/variants")
        assert hidden_entry.status_code == 404
        assert "entry not found" in hidden_entry.json()["detail"]

        missing_project_orphans = client.get("/api/projects/999/orphan-variants")
        assert missing_project_orphans.status_code == 404
        assert "project not found" in missing_project_orphans.json()["detail"]


def test_orphan_variants_route_lists_project_orphans() -> None:
    with TestClient(app) as client:
        assert client.post("/api/demo/reset").status_code == 200
        entries = EntryService()
        variants = VariantCatalogService()
        lifecycle = VariantLifecycleService()

        entry = entries.get_or_create_entry("orphan.visible", project_id=DEFAULT_PROJECT_ID)
        variant_id = variants.create_variant(
            int(entry["entry_id"]),
            "debug/orphan.xlsx",
            "Orphan visible source",
            {"fr": "Orphan visible target"},
            {"context": "debug"},
        )
        lifecycle.refresh_orphan_states(int(entry["entry_id"]))

        response = client.get("/api/projects/1/orphan-variants")
        assert response.status_code == 200
        payload = response.json()
        orphan_rows = {row["business_key"]: row for row in payload["results"]}
        assert "orphan.visible" in orphan_rows
        assert orphan_rows["orphan.visible"]["variant_id"] == variant_id
        assert orphan_rows["orphan.visible"]["orphaned_at"] is not None
        assert orphan_rows["orphan.visible"]["translations"]["fr"] == "Orphan visible target"


def test_negative_path_api_responses_cover_p0_safety_cases(tmp_path) -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/api/demo/reset").status_code == 200
        sample_root = Path(DemoService().sample_paths("core-cycle")["root"])

        promote_missing_version = client.post("/api/projects/1/promote/preview", json={})
        assert promote_missing_version.status_code == 422

        promote_unknown_version = client.post(
            "/api/projects/1/promote/execute",
            json={"version": "9.9.9"},
        )
        assert promote_unknown_version.status_code == 400
        assert "dev version not found" in promote_unknown_version.json()["detail"]

        invalid_fill_lang = _upload_folder(
            client,
            "/api/projects/1/fill/upload-folder",
            sample_root / "fill_source",
            extra_fields=[("lang", "de")],
        )
        assert invalid_fill_lang.status_code == 400
        assert "unsupported language column" in invalid_fill_lang.json()["detail"]

        missing_qa_dir = client.post(
            "/api/projects/1/qa",
            json={"source_dir": str(tmp_path / "missing"), "lang": "fr"},
        )
        assert missing_qa_dir.status_code == 400
        assert "qa source directory not found" in missing_qa_dir.json()["detail"]

        empty_preview = client.post(
            "/api/imports/upload-folder/preview",
            files=[
                (
                    "files",
                    (
                        "empty.xlsx",
                        b"",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                ("relative_paths", (None, "nested/empty.xlsx")),
            ],
        )
        assert empty_preview.status_code == 400
        assert "empty upload file" in empty_preview.json()["detail"]

        invalid_relative_path = client.post(
            "/api/imports/upload-folder/preview",
            files=[
                (
                    "files",
                    (
                        "bad.xlsx",
                        b"not-empty",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                ("relative_paths", (None, "../bad.xlsx")),
            ],
        )
        assert invalid_relative_path.status_code == 400
        assert "invalid relative path" in invalid_relative_path.json()["detail"]

        invalid_project_payloads = [
            {
                "name": "Bad Project Blank",
                "translation_columns": ["fr", " "],
                "remark_columns": ["context"],
            },
            {
                "name": "Bad Project Duplicate",
                "translation_columns": ["fr", "fr"],
                "remark_columns": ["context"],
            },
            {
                "name": "Bad Project Fixed",
                "translation_columns": ["file_name"],
                "remark_columns": ["context"],
            },
        ]
        for payload in invalid_project_payloads:
            response = client.post("/api/projects", json=payload)
            assert response.status_code == 400
            assert any(
                fragment in response.json()["detail"]
                for fragment in [
                    "schema columns",
                    "blank column name",
                    "duplicate column",
                ]
            )


def test_default_project_compatibility_routes_still_work() -> None:
    with TestClient(app) as client:
        assert client.post("/api/demo/reset").status_code == 200
        sample_root = Path(DemoService().sample_paths("core-cycle")["root"])

        state_response = client.get("/api/state")
        assert state_response.status_code == 200
        state_payload = state_response.json()
        assert state_payload["project"]["project_id"] == 1
        assert state_payload["samples"]

        strings_response = client.get("/api/strings")
        assert strings_response.status_code == 200
        assert any(item["business_key"] == "common.welcome" for item in strings_response.json())

        import_response = client.post(
            "/api/imports/directory",
            json={"input_dir": str(sample_root / "import_bundle")},
        )
        assert import_response.status_code == 200
        import_job = import_response.json()
        batch_id = import_job["job"]["summary"]["import_batch_id"]
        assert import_job["job"]["project_id"] == 1

        report_response = client.get(f"/api/imports/{batch_id}/report")
        assert report_response.status_code == 200
        assert report_response.json()["summary"]["import_batch_id"] == batch_id

        dev_import_response = client.post(
            "/api/dev-versions/import",
            json={
                "import_batch_id": batch_id,
                "version": "2.2.3",
                "mark_as_candidate": True,
            },
        )
        assert dev_import_response.status_code == 200
        dev_job_id = dev_import_response.json()["job"]["job_id"]

        job_detail = client.get(f"/api/jobs/{dev_job_id}")
        assert job_detail.status_code == 200
        assert job_detail.json()["job"]["project_id"] == 1

        job_report = client.get(f"/api/jobs/{dev_job_id}/report")
        assert job_report.status_code == 200
        assert job_report.json()["summary"]["processed_count"] == 4
        assert job_report.json()["summary"]["stages"][0]["stage"] == "bind_dev_scope"


def test_job_stage_summaries_are_attached_to_long_running_flows() -> None:
    with TestClient(app) as client:
        assert client.post("/api/demo/reset").status_code == 200
        sample_root = Path(DemoService().sample_paths("core-cycle")["root"])

        import_response = client.post(
            "/api/imports/directory",
            json={"input_dir": str(sample_root / "import_bundle")},
        )
        assert import_response.status_code == 200
        import_stages = import_response.json()["job"]["summary"]["stages"]
        assert [stage["stage"] for stage in import_stages] == ["parse", "persist_import"]

        batch_id = import_response.json()["job"]["summary"]["import_batch_id"]
        dev_import_response = client.post(
            "/api/dev-versions/import",
            json={"import_batch_id": batch_id, "version": "2.2.3", "mark_as_candidate": True},
        )
        assert dev_import_response.status_code == 200
        assert dev_import_response.json()["job"]["summary"]["stages"][0]["stage"] == "bind_dev_scope"

        fill_response = _upload_folder(
            client,
            "/api/projects/1/fill/upload-folder",
            sample_root / "fill_source",
            extra_fields=[("lang", "fr")],
        )
        assert fill_response.status_code == 200
        assert [stage["stage"] for stage in fill_response.json()["job"]["summary"]["stages"]] == [
            "fill_export",
            "artifact_write",
        ]

        qa_response = _upload_folder(
            client,
            "/api/projects/1/qa/upload-folder",
            sample_root / "fill_source",
            extra_fields=[("lang", "fr")],
        )
        assert qa_response.status_code == 200
        assert qa_response.json()["job"]["summary"]["stages"][0]["stage"] == "qa_scan"
