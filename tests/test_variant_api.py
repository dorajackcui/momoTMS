from io import BytesIO
from pathlib import Path
import time

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.db import get_db_path
from app.main import app
from app.services.demo.service import DemoService
from app.services.imports.service import ImportService


def reset_demo() -> None:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    DemoService().reset()


def build_workbook_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def wait_for_job(
    client: TestClient,
    job_detail: dict,
    *,
    project_id: int = 1,
    timeout_seconds: float = 5.0,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    current = job_detail
    while current["job"]["status"] == "running":
        if time.monotonic() >= deadline:
            raise AssertionError(f"job #{current['job']['job_id']} did not finish within {timeout_seconds} seconds")
        time.sleep(0.05)
        response = client.get(f"/api/projects/{project_id}/jobs/{current['job']['job_id']}")
        assert response.status_code == 200
        current = response.json()
    return current


def test_branch_routes_and_removed_compatibility_surface() -> None:
    reset_demo()
    sample = DemoService().get_sample("core-cycle")
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    with TestClient(app) as client:
        state_response = client.get("/api/projects/1/state")
        assert state_response.status_code == 200
        state_payload = state_response.json()
        assert "release_summary" in state_payload
        assert "candidate_dev_branch" in state_payload
        assert "dev_branches" in state_payload
        assert "rel_summary" not in state_payload
        assert "dev_versions" not in state_payload

        mutation = client.post(
            "/api/projects/1/branches/mutations",
            json={
                "branch_ref": f"dev/{sample['dev_version']}",
                "input": {
                    "kind": "import_batch",
                    "import_batch_id": batch["import_batch_id"],
                    "mark_as_candidate_release": True,
                },
            },
        )
        assert mutation.status_code == 200
        mutation_detail = wait_for_job(client, mutation.json())
        assert mutation_detail["job"]["status"] == "success"

        branches_response = client.get("/api/projects/1/branches", params={"lang": "fr"})
        assert branches_response.status_code == 200
        branches = branches_response.json()["branches"]
        assert any(item["branch_ref"] == "rel/current" for item in branches)
        assert any(item["branch_ref"] == f"dev/{sample['dev_version']}" for item in branches)

        compare_response = client.get(
            "/api/projects/1/branches/compare",
            params={
                "base_branch_ref": "rel/current",
                "target_branch_ref": f"dev/{sample['dev_version']}",
                "lang": "fr",
            },
        )
        assert compare_response.status_code == 200
        compare_payload = compare_response.json()
        assert compare_payload["base_branch_ref"] == "rel/current"
        assert compare_payload["target_branch_ref"] == f"dev/{sample['dev_version']}"

        queue_response = client.get(
            "/api/projects/1/branches/queue",
            params={"target_branch_ref": f"dev/{sample['dev_version']}", "lang": "fr"},
        )
        assert queue_response.status_code == 200
        assert queue_response.json()["target_branch_ref"] == f"dev/{sample['dev_version']}"

        master_response = client.get("/api/projects/1/branches/master/entries/rel.locked.same")
        assert master_response.status_code == 200
        assert any(row["branch_ref"] == "rel/current" for row in master_response.json()["results"])

        replace_preview = client.post(
            "/api/projects/1/branches/replace/preview",
            json={
                "source_branch_ref": f"dev/{sample['dev_version']}",
                "target_branch_ref": "rel/current",
            },
        )
        assert replace_preview.status_code == 200
        assert replace_preview.json()["source_branch_ref"] == f"dev/{sample['dev_version']}"

        assert client.post("/api/projects/1/branches/dev/import", json={}).status_code == 405
        assert client.post(f"/api/projects/1/branches/dev/{sample['dev_version']}/promote/preview").status_code == 404

        assert client.get("/variant-workbench").status_code == 410
        assert client.get("/workbench").status_code == 410
        assert client.get("/api/state").status_code == 404
        assert client.get("/api/strings").status_code == 404
        assert client.get("/api/scopes/compare").status_code == 404


def test_branch_read_routes_return_404_for_missing_project() -> None:
    reset_demo()

    with TestClient(app) as client:
        responses = [
            client.get("/api/projects/999/branches"),
            client.get(
                "/api/projects/999/branches/compare",
                params={"base_branch_ref": "rel/current", "target_branch_ref": "dev/2.4.1"},
            ),
            client.get("/api/projects/999/branches/queue", params={"target_branch_ref": "dev/2.4.1"}),
            client.get("/api/projects/999/branches/master/entries/common.welcome"),
            client.get("/api/projects/999/branches/master/search", params={"source": "Welcome {0}"}),
            client.get("/api/projects/999/branches/dev"),
        ]

    for response in responses:
        assert response.status_code == 404
        assert "project not found" in response.json()["detail"]


def test_import_upload_preview_uses_session_and_job_detail_returns_preview_rows() -> None:
    reset_demo()
    workbook_bytes = build_workbook_bytes(
        ["business_key", "source", "fr"],
        [[f"import.key.{index}", f"Source {index}", f"Target {index}"] for index in range(13)],
    )

    with TestClient(app) as client:
        preview = client.post(
            "/api/projects/1/imports/upload-folder/preview",
            files=[
                (
                    "files",
                    (
                        "messages.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                ("relative_paths", (None, "bundle/messages.xlsx")),
            ],
        )
        assert preview.status_code == 200
        preview_payload = preview.json()
        assert preview_payload["upload_session_id"]
        assert preview_payload["file_count"] == 1
        assert preview_payload["sheet_count"] == 1
        assert preview_payload["sheet_previews"][0]["missing_targets"] == []

        start_import = client.post(
            "/api/projects/1/imports/upload-folder",
            json={
                "upload_session_id": preview_payload["upload_session_id"],
                "column_mapping_json": "{}",
            },
        )
        assert start_import.status_code == 200
        job_detail = wait_for_job(client, start_import.json())
        assert job_detail["job"]["status"] == "success"
        import_batch_id = job_detail["job"]["summary"]["import_batch_id"]
        assert import_batch_id > 0

        preview_rows = job_detail["report"]["rows"]
        assert len(preview_rows) == 12
        assert preview_rows[0]["business_key"] == "import.key.0"
        assert preview_rows[-1]["business_key"] == "import.key.11"

        full_report = client.get(f"/api/projects/1/imports/{import_batch_id}/report")
        assert full_report.status_code == 200
        assert len(full_report.json()["rows"]) == 13

        consumed_session = client.post(
            "/api/projects/1/imports/upload-folder",
            json={
                "upload_session_id": preview_payload["upload_session_id"],
                "column_mapping_json": "{}",
            },
        )
        assert consumed_session.status_code == 404
        assert "upload session not found" in consumed_session.json()["detail"]


def test_import_upload_folder_rejects_missing_session() -> None:
    reset_demo()

    with TestClient(app) as client:
        response = client.post(
            "/api/projects/1/imports/upload-folder",
            json={
                "upload_session_id": "missing-session",
                "column_mapping_json": "{}",
            },
        )

    assert response.status_code == 404
    assert "upload session not found" in response.json()["detail"]


def test_fill_upload_folder_requires_selected_target_lang_header() -> None:
    reset_demo()
    workbook_bytes = build_workbook_bytes(
        ["business_key", "source"],
        [["common.welcome", "Welcome {0}"]],
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/projects/1/fill/upload-folder",
            files=[
                (
                    "files",
                    (
                        "fill.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                ("relative_paths", (None, "bundle/fill.xlsx")),
                ("lang", (None, "fr")),
            ],
        )

    assert response.status_code == 400
    assert "workbook missing required header: fr" in response.json()["detail"]


def test_qa_upload_folder_requires_selected_target_lang_header() -> None:
    reset_demo()
    workbook_bytes = build_workbook_bytes(
        ["business_key", "source"],
        [["common.welcome", "Welcome {0}"]],
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/projects/1/qa/upload-folder",
            files=[
                (
                    "files",
                    (
                        "qa.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                ("relative_paths", (None, "bundle/qa.xlsx")),
                ("lang", (None, "fr")),
            ],
        )

    assert response.status_code == 400
    assert "workbook missing required header: fr" in response.json()["detail"]
