from pathlib import Path

from fastapi.testclient import TestClient

from app.db import get_db_path
from app.main import app
from app.services.demo.service import DemoService
from app.services.imports.service import ImportService


def reset_demo() -> None:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    DemoService().reset()


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
                "scope_ref": f"dev/{sample['dev_version']}",
                "input": {
                    "kind": "import_batch",
                    "import_batch_id": batch["import_batch_id"],
                    "mark_as_candidate_release": True,
                },
            },
        )
        assert mutation.status_code == 200

        branches_response = client.get("/api/projects/1/branches", params={"lang": "fr"})
        assert branches_response.status_code == 200
        scopes = branches_response.json()["scopes"]
        assert any(item["scope_ref"] == "rel/current" for item in scopes)
        assert any(item["scope_ref"] == f"dev/{sample['dev_version']}" for item in scopes)

        compare_response = client.get(
            "/api/projects/1/branches/compare",
            params={
                "base_scope_ref": "rel/current",
                "target_scope_ref": f"dev/{sample['dev_version']}",
                "lang": "fr",
            },
        )
        assert compare_response.status_code == 200
        compare_payload = compare_response.json()
        assert compare_payload["base_scope_ref"] == "rel/current"
        assert compare_payload["target_scope_ref"] == f"dev/{sample['dev_version']}"

        queue_response = client.get(
            "/api/projects/1/branches/queue",
            params={"target_scope_ref": f"dev/{sample['dev_version']}", "lang": "fr"},
        )
        assert queue_response.status_code == 200
        assert queue_response.json()["target_scope_ref"] == f"dev/{sample['dev_version']}"

        master_response = client.get("/api/projects/1/branches/master/entries/rel.locked.same")
        assert master_response.status_code == 200
        assert any(row["scope_ref"] == "rel/current" for row in master_response.json()["results"])

        sync_preview = client.post(
            "/api/projects/1/branches/sync/preview",
            json={
                "source_scope_ref": f"dev/{sample['dev_version']}",
                "target_scope_ref": "rel/current",
            },
        )
        assert sync_preview.status_code == 200
        assert sync_preview.json()["source_scope_ref"] == f"dev/{sample['dev_version']}"

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
                params={"base_scope_ref": "rel/current", "target_scope_ref": "dev/1.0.0"},
            ),
            client.get("/api/projects/999/branches/queue", params={"target_scope_ref": "dev/1.0.0"}),
            client.get("/api/projects/999/branches/master/entries/common.welcome"),
            client.get("/api/projects/999/branches/master/search", params={"source": "Welcome {0}"}),
            client.get("/api/projects/999/branches/dev"),
        ]

    for response in responses:
        assert response.status_code == 404
        assert "project not found" in response.json()["detail"]
