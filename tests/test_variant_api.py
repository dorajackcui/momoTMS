from io import BytesIO
from pathlib import Path
import time

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.db import get_db_path
from app.main import app
from app.services.branch.models import BranchRef
from app.services.branch.registry import BranchRegistryService
from app.services.demo.service import DemoService
from app.services.imports.service import ImportService
from app.services.project.service import ProjectService
from app.services.read_models.repository import ReadModelRepository
from app.services.read_models.selectors import VariantFilter
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.state_coordinator import VariantStateCoordinator
from app.services.workflows.trash_restore import TrashRestoreService
from tests.service_helpers import branch_services


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


def create_bound_variant(
    *,
    project_id: int,
    business_key: str,
    source: str,
    translations: dict[str, str],
    branch_refs: list[BranchRef],
) -> int:
    entries = EntryService()
    catalog = VariantCatalogService()
    bindings = VariantStateCoordinator()
    entry = entries.get_or_create_entry(business_key, project_id=project_id)
    variant_id = catalog.create_variant(
        int(entry["entry_id"]),
        catalog.build_content(
            f"{business_key}.xlsx",
            source,
            translations,
            {"context": business_key},
        ),
    )
    for branch_ref in branch_refs:
        if branch_ref.is_dev:
            BranchRegistryService().ensure_dev_branch(branch_ref.version, project_id=project_id)
        bindings.bind(int(entry["entry_id"]), branch_ref, variant_id)
    return variant_id


def test_scope_routes_and_removed_compatibility_surface() -> None:
    reset_demo()
    sample = DemoService().get_sample("core-cycle")
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    with TestClient(app) as client:
        state_response = client.get("/api/projects/1/state")
        assert state_response.status_code == 200
        state_payload = state_response.json()
        assert "release_summary" in state_payload
        assert "candidate_dev_branch" not in state_payload
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

        master_rows_response = client.get("/api/projects/1/scopes/master/rows")
        assert master_rows_response.status_code == 200
        master_rows_payload = master_rows_response.json()
        assert master_rows_payload["scope_ref"] == "master"
        assert any(row["state"] == "orphan" for row in master_rows_payload["rows"])
        assert any(row["business_key"] == "common.welcome" for row in master_rows_payload["rows"])

        rel_rows_response = client.get("/api/projects/1/scopes/rel/current/rows")
        assert rel_rows_response.status_code == 200
        assert all(
            any(binding["branch_ref"] == "rel/current" for binding in row["bindings"])
            for row in rel_rows_response.json()["rows"]
        )

        dev_lookup_response = client.get(
            f"/api/projects/1/scopes/dev/{sample['dev_version']}/lookup",
            params={"business_key": "dev.mutable"},
        )
        assert dev_lookup_response.status_code == 200
        dev_lookup_payload = dev_lookup_response.json()
        assert dev_lookup_payload["scope_ref"] == f"dev/{sample['dev_version']}"
        assert dev_lookup_payload["mode"] == "business_key"
        assert [row["business_key"] for row in dev_lookup_payload["rows"]] == ["dev.mutable"]

        master_response = client.get("/api/projects/1/branches/master/entries/rel.locked.same")
        assert master_response.status_code == 200
        assert all(row["scope_ref"] == "master" for row in master_response.json()["results"])

        replace_preview = client.post(
            "/api/projects/1/branches/replace/preview",
            json={
                "source_branch_ref": f"dev/{sample['dev_version']}",
                "target_branch_ref": "rel/current",
            },
        )
        assert replace_preview.status_code == 200
        replace_preview_payload = replace_preview.json()
        assert replace_preview_payload["preview_kind"] == "effect_forecast"
        assert replace_preview_payload["workflow_kind"] == "branch_replace"
        assert replace_preview_payload["request_echo"]["source_branch_ref"] == f"dev/{sample['dev_version']}"
        assert replace_preview_payload["summary"]["final_target_entry_count"] >= 4
        assert "cleanup_binding_count" not in replace_preview_payload["summary"]

        assert client.post("/api/projects/1/branches/dev/import", json={}).status_code == 405
        assert client.post(f"/api/projects/1/branches/dev/{sample['dev_version']}/promote/preview").status_code == 404

        assert client.get("/variant-workbench").status_code == 410
        assert client.get("/workbench").status_code == 410
        assert client.get("/api/state").status_code == 404
        assert client.get("/api/strings").status_code == 404
        assert client.get("/api/projects/1/branches/compare").status_code == 404
        assert client.get("/api/projects/1/branches/queue").status_code == 404
        assert client.get("/api/scopes/compare").status_code == 404


def test_import_batch_mutation_rejects_candidate_flag() -> None:
    reset_demo()
    sample = DemoService().get_sample("core-cycle")
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    with TestClient(app) as client:
        response = client.post(
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

    assert response.status_code == 422


def test_branch_replace_preview_and_execute_report_rebind_target_when_variant_ids_differ() -> None:
    reset_demo()
    business_key = "replace.rebind"
    create_bound_variant(
        project_id=1,
        business_key=business_key,
        source="Source branch content",
        translations={"fr": "Source branch"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )
    create_bound_variant(
        project_id=1,
        business_key=business_key,
        source="Target branch content",
        translations={"fr": "Target branch"},
        branch_refs=[BranchRef.rel_current()],
    )

    with TestClient(app) as client:
        preview_response = client.post(
            "/api/projects/1/branches/replace/preview",
            json={
                "source_branch_ref": "dev/2.4.3",
                "target_branch_ref": "rel/current",
            },
        )
        execute_response = client.post(
            "/api/projects/1/branches/replace/execute",
            json={
                "source_branch_ref": "dev/2.4.3",
                "target_branch_ref": "rel/current",
            },
        )

    assert preview_response.status_code == 200
    payload = preview_response.json()
    row = next(item for item in payload["rows"] if item["business_key"] == business_key)
    assert payload["preview_kind"] == "effect_forecast"
    assert payload["workflow_kind"] == "branch_replace"
    assert payload["request_echo"] == {
        "source_branch_ref": "dev/2.4.3",
        "target_branch_ref": "rel/current",
    }
    assert row["status"] == "REBIND_TARGET"
    assert row["binding_effect"] == "rebind"
    assert row["variant_resolution"] == "reuse_existing"
    assert row["row_outcome"] == "applied"
    assert payload["summary"]["final_target_entry_count"] == 1
    assert payload["summary"]["added_to_target_count"] == 0
    assert payload["summary"]["kept_in_target_count"] == 0
    assert payload["summary"]["rebind_target_count"] == 1
    assert payload["summary"]["removed_from_target_count"] == 5
    assert "cleanup_binding_count" not in payload["summary"]
    assert "binding_effect_counts" not in payload["summary"]
    assert "variant_resolution_counts" not in payload["summary"]
    assert "row_outcome_counts" not in payload["summary"]
    assert "already_in_target_count" not in payload["summary"]

    assert execute_response.status_code == 200
    execute_detail = execute_response.json()
    summary = execute_detail["job"]["summary"]
    execute_row = next(item for item in execute_detail["report"]["rows"] if item["business_key"] == business_key)
    assert execute_row["status"] == "REBIND_TARGET"
    assert execute_row["binding_effect"] == "rebind"
    assert execute_row["variant_resolution"] == "reuse_existing"
    assert execute_row["row_outcome"] == "applied"
    assert summary["final_target_entry_count"] == 1
    assert summary["added_to_target_count"] == 0
    assert summary["kept_in_target_count"] == 0
    assert summary["rebind_target_count"] == 1
    assert summary["removed_from_target_count"] == 5
    assert "cleanup_binding_count" not in summary
    assert "binding_effect_counts" not in summary
    assert "variant_resolution_counts" not in summary
    assert "row_outcome_counts" not in summary
    assert "already_in_target_count" not in summary


def test_scope_read_routes_return_404_for_missing_project() -> None:
    reset_demo()

    with TestClient(app) as client:
        responses = [
            client.get("/api/projects/999/variants"),
            client.get("/api/projects/999/branches"),
            client.get("/api/projects/999/scopes/master/rows"),
            client.get("/api/projects/999/scopes/rel/current/rows"),
            client.get("/api/projects/999/scopes/master/lookup", params={"business_key": "common.welcome"}),
            client.get(
                "/api/projects/999/history/same-source-candidates",
                params={"business_key": "common.welcome", "source": "Welcome {0}"},
            ),
            client.get("/api/projects/999/branches/master/entries/common.welcome"),
            client.get("/api/projects/999/branches/master/search", params={"source": "Welcome {0}"}),
            client.get("/api/projects/999/branches/dev"),
        ]

    for response in responses:
        assert response.status_code == 404
        assert "project not found" in response.json()["detail"]


def test_project_creation_and_bootstrap_expose_single_pivot_schema() -> None:
    reset_demo()

    with TestClient(app) as client:
        create_response = client.post(
            "/api/projects",
            json={
                "name": "Pivot API Project",
                "translation_columns": ["fr", "en", "de"],
                "remark_columns": ["context"],
                "pivot_language": "en",
                "pivoted_languages": ["fr"],
            },
        )
        assert create_response.status_code == 200
        project = create_response.json()

        state_response = client.get(f"/api/projects/{project['project_id']}/state")
        assert state_response.status_code == 200
        schema = state_response.json()["schema"]
        assert schema["pivot_language"] == "en"
        assert schema["pivoted_languages"] == ["fr"]
        assert "translation_pivots" not in schema


def test_branch_bootstrap_api_runs_async_and_exposes_bootstrap_metadata(tmp_path) -> None:
    reset_demo()
    business_key = "bootstrap.api.reuse"
    source = "Bootstrap source"
    create_bound_variant(
        project_id=1,
        business_key=business_key,
        source=source,
        translations={"fr": "Existing bootstrap content"},
        branch_refs=[BranchRef.rel_current()],
    )

    import_root = tmp_path / "branch-bootstrap-api"
    workbook_path = import_root / "bundle" / "branch-bootstrap.xlsx"
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    workbook_path.write_bytes(
        build_workbook_bytes(
            ["business_key", "source", "fr", "context"],
            [[business_key, source, "Uploaded bootstrap content", "bootstrap"]],
        )
    )
    batch = ImportService().import_directory(str(import_root))

    with TestClient(app) as client:
        response = client.post(
            "/api/projects/1/branches/bootstrap",
            json={
                "branch_ref": "dev/2.4.3",
                "import_batch_id": batch["import_batch_id"],
            },
        )
        assert response.status_code == 200
        detail = wait_for_job(client, response.json())

        branch_response = client.get("/api/projects/1/branches/dev/2.4.3")
        state_response = client.get("/api/projects/1/state")
        assert branch_response.status_code == 200
        assert state_response.status_code == 200

    assert detail["job"]["job_type"] == "branch_bootstrap"
    assert detail["job"]["summary"]["input_kind"] == "bootstrap"
    assert detail["job"]["summary"]["bound_existing_variant_count"] == 1
    assert detail["report"]["rows"][0]["status"] == "BOUND_EXISTING_VARIANT"

    branch_detail = branch_response.json()
    assert branch_detail["bootstrap_state"] == "bootstrapped"
    assert branch_detail["bootstrap_import_batch_id"] == batch["import_batch_id"]
    assert branch_detail["bootstrap_job_id"] == detail["job"]["job_id"]
    assert branch_detail["bootstrapped_at"] is not None

    state_payload = state_response.json()
    dev_branch = next(
        (item for item in state_payload["dev_branches"] if item["version"] == "2.4.3"),
        None,
    )
    assert dev_branch is not None, "expected dev branch summary for version 2.4.3"
    assert "is_candidate_release" not in dev_branch
    assert "promoted_at" not in dev_branch
    assert dev_branch["bootstrap_state"] == "bootstrapped"
    assert dev_branch["bootstrap_import_batch_id"] == batch["import_batch_id"]
    assert dev_branch["bootstrap_job_id"] == detail["job"]["job_id"]
    assert dev_branch["bootstrapped_at"] is not None


def test_branch_mutation_preview_api_is_read_only_for_direct_input() -> None:
    reset_demo()
    business_key = "preview.api.direct"
    variant_id = create_bound_variant(
        project_id=1,
        business_key=business_key,
        source="Preview API source",
        translations={"fr": "Original API preview text"},
        branch_refs=[BranchRef.rel_current()],
    )

    with TestClient(app) as client:
        before_jobs = client.get("/api/projects/1/jobs")
        assert before_jobs.status_code == 200

        response = client.post(
            "/api/projects/1/branches/mutations/preview",
            json={
                "branch_ref": "rel/current",
                "input": {
                    "kind": "direct",
                    "changes": [
                        {
                            "business_key": business_key,
                            "translations_by_lang": {"fr": "Preview API changed"},
                        }
                    ],
                },
            },
        )

        after_jobs = client.get("/api/projects/1/jobs")
        assert after_jobs.status_code == 200

    assert response.status_code == 200
    payload = response.json()
    row = payload["rows"][0]
    variant = VariantCatalogService().get_variant(variant_id)
    assert payload["preview_kind"] == "effect_forecast"
    assert payload["workflow_kind"] == "branch_mutation"
    assert payload["request_echo"]["branch_ref"] == "rel/current"
    assert payload["request_echo"]["input_kind"] == "direct"
    assert row["status"] == "UPDATED_BOUND_VARIANT"
    assert row["binding_effect"] == "none"
    assert row["variant_resolution"] == "stay_current"
    assert row["row_outcome"] == "applied"
    assert payload["summary"]["variant_resolution_counts"]["stay_current_count"] == 1
    assert variant["translations"]["fr"] == "Original API preview text"
    assert after_jobs.json() == before_jobs.json()


def test_branch_bootstrap_preview_api_is_read_only_and_reports_reuse_existing(tmp_path) -> None:
    reset_demo()
    BranchRegistryService().ensure_dev_branch("2.4.3", project_id=1)
    business_key = "bootstrap.preview.api.reuse"
    source = "Bootstrap preview source"
    create_bound_variant(
        project_id=1,
        business_key=business_key,
        source=source,
        translations={"fr": "Existing bootstrap preview content"},
        branch_refs=[BranchRef.rel_current()],
    )

    import_root = tmp_path / "branch-bootstrap-preview-api"
    workbook_path = import_root / "bundle" / "branch-bootstrap-preview.xlsx"
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    workbook_path.write_bytes(
        build_workbook_bytes(
            ["business_key", "source", "fr", "context"],
            [[business_key, source, "Uploaded bootstrap preview content", "bootstrap-preview"]],
        )
    )
    batch = ImportService().import_directory(str(import_root))

    with TestClient(app) as client:
        before_jobs = client.get("/api/projects/1/jobs")
        assert before_jobs.status_code == 200

        response = client.post(
            "/api/projects/1/branches/bootstrap/preview",
            json={
                "branch_ref": "dev/2.4.3",
                "import_batch_id": batch["import_batch_id"],
            },
        )

        after_jobs = client.get("/api/projects/1/jobs")
        branch_response = client.get("/api/projects/1/branches/dev/2.4.3")
        assert after_jobs.status_code == 200
        assert branch_response.status_code == 200
        assert branch_response.json()["bootstrap_state"] == "not_bootstrapped"

    assert response.status_code == 200
    payload = response.json()
    row = payload["rows"][0]
    assert payload["preview_kind"] == "effect_forecast"
    assert payload["workflow_kind"] == "branch_bootstrap"
    assert payload["request_echo"]["branch_ref"] == "dev/2.4.3"
    assert payload["request_echo"]["import_batch_id"] == batch["import_batch_id"]
    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert row["binding_effect"] == "bind"
    assert row["variant_resolution"] == "reuse_existing"
    assert row["row_outcome"] == "applied"
    assert payload["summary"]["bound_existing_variant_count"] == 1
    assert payload["summary"]["variant_resolution_counts"]["reuse_existing_count"] == 1
    assert after_jobs.json() == before_jobs.json()


def test_branch_bootstrap_api_rejects_rel_current() -> None:
    reset_demo()
    sample = DemoService().get_sample("core-cycle")
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    with TestClient(app) as client:
        before_jobs = client.get("/api/projects/1/jobs")
        assert before_jobs.status_code == 200
        response = client.post(
            "/api/projects/1/branches/bootstrap",
            json={
                "branch_ref": "rel/current",
                "import_batch_id": batch["import_batch_id"],
            },
        )
        after_jobs = client.get("/api/projects/1/jobs")
        assert after_jobs.status_code == 200

    assert response.status_code == 400
    assert "dev" in response.json()["detail"].lower()
    assert after_jobs.json() == before_jobs.json()


def test_branch_bootstrap_api_rejects_already_bootstrapped_without_creating_job() -> None:
    reset_demo()
    sample = DemoService().get_sample("core-cycle")
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    with TestClient(app) as client:
        first_response = client.post(
            "/api/projects/1/branches/bootstrap",
            json={
                "branch_ref": f"dev/{sample['dev_version']}",
                "import_batch_id": batch["import_batch_id"],
            },
        )
        assert first_response.status_code == 200
        wait_for_job(client, first_response.json())

        before_jobs = client.get("/api/projects/1/jobs")
        assert before_jobs.status_code == 200

        second_response = client.post(
            "/api/projects/1/branches/bootstrap",
            json={
                "branch_ref": f"dev/{sample['dev_version']}",
                "import_batch_id": batch["import_batch_id"],
            },
        )

        after_jobs = client.get("/api/projects/1/jobs")
        assert after_jobs.status_code == 200

    assert second_response.status_code == 400
    assert "already bootstrapped" in second_response.json()["detail"].lower()
    assert after_jobs.json() == before_jobs.json()


def test_scope_history_same_source_candidates_exclude_trashed() -> None:
    reset_demo()
    trash_restore = TrashRestoreService()

    # Delete and project_trash to actually trash the variant
    trash_restore.delete(BranchRef.rel_current(), ["common.welcome"])
    trash_restore.project_trash(["common.welcome"])

    # Verify trashed variant is excluded from same-source
    with TestClient(app) as client:
        response = client.get(
            "/api/projects/1/history/same-source-candidates",
            params={"business_key": "common.welcome", "source": "Welcome {0}"},
        )
        assert response.status_code == 200
        rows = response.json()["rows"]
        variant_ids = {row["variant_id"] for row in rows}
        # The trashed variant should not appear
        assert len(rows) == 0  # Only variant was trashed


def test_project_variants_route_supports_state_filters_and_project_scope() -> None:
    reset_demo()
    services = branch_services()
    project = ProjectService().create_project("Second Project", ["fr"], ["context"])
    project_id = int(project["project_id"])
    entry = EntryService().get_or_create_entry("other.project.key", project_id=project_id)
    variant_id = VariantCatalogService().create_variant(
        int(entry["entry_id"]),
        VariantCatalogService().build_content(
            "other.xlsx",
            "Other source",
            {"fr": "Autre"},
            {"context": "other project"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.rel_current(), variant_id)

    with TestClient(app) as client:
        active_response = client.get("/api/projects/1/variants")
        assert active_response.status_code == 200
        active_payload = active_response.json()
        active_keys = {row["business_key"] for row in active_payload["rows"]}
        assert active_payload["page"] == 1
        assert active_payload["page_size"] == active_payload["total_rows"]
        assert all(row["state"] == "active" for row in active_payload["rows"])
        assert "common.welcome" in active_keys
        assert "dev.mutable" not in active_keys
        assert "other.project.key" not in active_keys

        orphan_response = client.get("/api/projects/1/variants", params={"state": "orphan"})
        assert orphan_response.status_code == 200
        orphan_payload = orphan_response.json()
        orphan_keys = {row["business_key"] for row in orphan_payload["rows"]}
        assert orphan_keys == {"dev.mutable", "fill.master_only", "trash.me"}
        assert all(row["state"] == "orphan" for row in orphan_payload["rows"])

        all_response = client.get("/api/projects/1/variants", params={"state": "all"})
        assert all_response.status_code == 200
        all_payload = all_response.json()
        all_keys = {row["business_key"] for row in all_payload["rows"]}
        assert active_keys.issubset(all_keys)
        assert orphan_keys.issubset(all_keys)
        assert "other.project.key" not in all_keys

        second_project_response = client.get(f"/api/projects/{project_id}/variants")
        assert second_project_response.status_code == 200
        assert [row["business_key"] for row in second_project_response.json()["rows"]] == [
            "other.project.key"
        ]


def test_project_variants_route_supports_branch_filters_search_and_multi_bindings() -> None:
    reset_demo()
    services = branch_services()
    entry = services.entries.get_entry("common.welcome")
    assert entry is not None
    variant = services.catalog.list_variants(int(entry["entry_id"]), include_trashed=True)[0]
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.3"), int(variant["variant_id"]))

    with TestClient(app) as client:
        filtered_response = client.get(
            "/api/projects/1/variants",
            params=[
                ("state", "all"),
                ("branch_ref", "rel/current"),
                ("branch_ref", "dev/2.4.3"),
                ("search_business_key", "COMMON"),
                ("search_source", "welcome"),
            ],
        )
        assert filtered_response.status_code == 200
        filtered_payload = filtered_response.json()
        assert filtered_payload["total_rows"] == 1
        row = filtered_payload["rows"][0]
        assert row["business_key"] == "common.welcome"
        assert row["state"] == "active"
        assert [binding["branch_ref"] for binding in row["bindings"]] == ["dev/2.4.3", "rel/current"]

        orphan_with_branch = client.get(
            "/api/projects/1/variants",
            params=[("state", "orphan"), ("branch_ref", "dev/2.4.3")],
        )
        assert orphan_with_branch.status_code == 200
        assert orphan_with_branch.json()["rows"] == []

        orphan_search = client.get(
            "/api/projects/1/variants",
            params={"state": "all", "search_business_key": "DEV.MUTABLE"},
        )
        assert orphan_search.status_code == 200
        assert orphan_search.json()["rows"][0]["state"] == "orphan"


def test_project_variants_route_excludes_trashed_variants_and_paginates_stably() -> None:
    reset_demo()
    services = branch_services()
    trash_restore = TrashRestoreService()
    entry = services.entries.get_entry("trash.me")
    assert entry is not None
    variant = services.catalog.list_variants(int(entry["entry_id"]), include_trashed=True)[0]
    services.bindings.bind(int(entry["entry_id"]), BranchRef.rel_current(), int(variant["variant_id"]))
    trash_restore.delete(BranchRef.rel_current(), ["trash.me"])
    trash_restore.project_trash(["trash.me"])

    with TestClient(app) as client:
        full_response = client.get("/api/projects/1/variants", params={"state": "all"})
        assert full_response.status_code == 200
        full_payload = full_response.json()
        full_keys = [row["business_key"] for row in full_payload["rows"]]
        full_ids = [row["variant_id"] for row in full_payload["rows"]]
        assert "trash.me" not in full_keys

        page_one = client.get(
            "/api/projects/1/variants",
            params={"state": "all", "page": 1, "page_size": 2},
        )
        assert page_one.status_code == 200
        page_one_payload = page_one.json()
        assert page_one_payload["page"] == 1
        assert page_one_payload["page_size"] == 2
        assert [row["variant_id"] for row in page_one_payload["rows"]] == full_ids[:2]

        page_two = client.get(
            "/api/projects/1/variants",
            params={"state": "all", "page": 2, "page_size": 2},
        )
        assert page_two.status_code == 200
        page_two_payload = page_two.json()
        assert page_two_payload["page"] == 2
        assert page_two_payload["page_size"] == 2
        assert [row["variant_id"] for row in page_two_payload["rows"]] == full_ids[2:4]


def test_project_variants_route_returns_dev_bound_rows_after_import_batch_apply() -> None:
    reset_demo()
    sample = DemoService().get_sample("core-cycle")
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    with TestClient(app) as client:
        mutation = client.post(
            "/api/projects/1/branches/mutations",
            json={
                "branch_ref": f"dev/{sample['dev_version']}",
                "input": {
                    "kind": "import_batch",
                    "import_batch_id": batch["import_batch_id"],
                },
            },
        )
        assert mutation.status_code == 200
        mutation_detail = wait_for_job(client, mutation.json())
        assert mutation_detail["job"]["status"] == "success"

        response = client.get(
            "/api/projects/1/variants",
            params={
                "state": "active",
                "branch_ref": f"dev/{sample['dev_version']}",
            },
        )
        assert response.status_code == 200
        keys = {row["business_key"] for row in response.json()["rows"]}
        assert "dev.mutable" in keys
        assert "dev.new.entry" in keys


def test_branch_mutation_api_authority_filtered_import_batch_reports_filtered_metadata(tmp_path) -> None:
    reset_demo()
    services = branch_services()
    entry = services.entries.get_or_create_entry("authority.api.filtered", project_id=1)
    actor_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "actor.xlsx",
            "Actor source",
            {"fr": "Actor content"},
            {"context": "actor"},
        ),
    )
    target_variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "target.xlsx",
            "Target source",
            {"fr": "Owner content"},
            {"context": "owner"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.5.1"), actor_variant_id)
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.2"), target_variant_id)

    import_root = tmp_path / "authority-api-filtered"
    workbook_path = import_root / "bundle" / "authority.xlsx"
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    workbook_path.write_bytes(
        build_workbook_bytes(
            ["business_key", "source", "fr", "context"],
            [["authority.api.filtered", "Target source", "Filtered by API", "Filtered by API"]],
        )
    )
    batch = ImportService().import_directory(str(import_root))

    with TestClient(app) as client:
        mutation = client.post(
            "/api/projects/1/branches/mutations",
            json={
                "branch_ref": "dev/2.5.1",
                "input": {
                    "kind": "import_batch",
                    "import_batch_id": batch["import_batch_id"],
                },
            },
        )
        assert mutation.status_code == 200
        detail = wait_for_job(client, mutation.json())

    assert detail["job"]["summary"]["content_filtered_by_authority_count"] == 1
    row = detail["report"]["rows"][0]
    assert row["status"] == "BOUND_EXISTING_VARIANT"
    assert row["content_filtered_by_authority"] is True
    assert services.catalog.get_variant(target_variant_id)["translations"]["fr"] == "Owner content"
    assert services.catalog.get_variant(target_variant_id)["remarks"]["context"] == "owner"


def test_branch_mutation_api_direct_reports_phase4_semantics() -> None:
    reset_demo()
    variant_id = create_bound_variant(
        project_id=1,
        business_key="api.direct.phase4",
        source="Direct source",
        translations={"fr": "Original direct text"},
        branch_refs=[BranchRef.rel_current()],
    )

    with TestClient(app) as client:
        mutation = client.post(
            "/api/projects/1/branches/mutations",
            json={
                "branch_ref": "rel/current",
                "input": {
                    "kind": "direct",
                    "changes": [
                        {
                            "business_key": "api.direct.phase4",
                            "translations_by_lang": {"fr": "Updated direct text"},
                        }
                    ],
                },
            },
        )
        assert mutation.status_code == 200
        detail = wait_for_job(client, mutation.json())
        assert detail["job"]["status"] == "success"

    direct_variant = VariantCatalogService().get_variant(variant_id)

    row = detail["report"]["rows"][0]
    assert row["status"] == "UPDATED_BOUND_VARIANT"
    assert row["mutation_class"] == "content"
    assert row["binding_effect"] == "none"
    assert row["content_effect"] == "update"
    assert row["row_outcome"] == "applied"
    assert direct_variant["translations"]["fr"] == "Updated direct text"
    assert detail["job"]["summary"]["mutation_class_counts"]["content_count"] == 1


def test_branch_mutation_api_import_batch_reports_phase4_semantics(tmp_path) -> None:
    reset_demo()
    variant_id = create_bound_variant(
        project_id=1,
        business_key="api.import.batch.phase4",
        source="Import source",
        translations={"fr": "Original import text"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )

    import_root = tmp_path / "api-import-batch-phase4"
    workbook_path = import_root / "bundle" / "phase4.xlsx"
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    workbook_path.write_bytes(
        build_workbook_bytes(
            ["business_key", "source", "fr", "context"],
            [["api.import.batch.phase4", "Import source", "Updated import text", "Updated import context"]],
        )
    )
    batch = ImportService().import_directory(str(import_root))

    with TestClient(app) as client:
        mutation = client.post(
            "/api/projects/1/branches/mutations",
            json={
                "branch_ref": "dev/2.4.3",
                "input": {
                    "kind": "import_batch",
                    "import_batch_id": batch["import_batch_id"],
                },
            },
        )
        assert mutation.status_code == 200
        detail = wait_for_job(client, mutation.json())
        assert detail["job"]["status"] == "success"

    import_variant = VariantCatalogService().get_variant(variant_id)

    row = detail["report"]["rows"][0]
    assert row["status"] == "UPDATED_BOUND_VARIANT"
    assert row["mutation_class"] == "content"
    assert row["binding_effect"] == "none"
    assert row["content_effect"] == "update"
    assert row["row_outcome"] == "applied"
    assert import_variant["translations"]["fr"] == "Updated import text"
    assert import_variant["remarks"]["context"] == "Updated import context"
    assert detail["job"]["summary"]["mutation_class_counts"]["content_count"] == 1
    assert detail["job"]["summary"]["binding_effect_counts"]["none_count"] == 1
    assert detail["job"]["summary"]["content_effect_counts"]["update_count"] == 1
    assert detail["job"]["summary"]["row_outcome_counts"]["applied_count"] == 1


def test_branch_rows_and_lookup_routes_match_existing_scope_routes() -> None:
    reset_demo()
    sample = DemoService().get_sample("core-cycle")
    batch = ImportService().import_directory(sample["paths"]["import_dir"])

    with TestClient(app) as client:
        mutation = client.post(
            "/api/projects/1/branches/mutations",
            json={
                "branch_ref": f"dev/{sample['dev_version']}",
                "input": {
                    "kind": "import_batch",
                    "import_batch_id": batch["import_batch_id"],
                },
            },
        )
        assert mutation.status_code == 200
        mutation_detail = wait_for_job(client, mutation.json())
        assert mutation_detail["job"]["status"] == "success"

        branch_rows_response = client.get(f"/api/projects/1/branches/dev/{sample['dev_version']}/rows")
        scope_rows_response = client.get(f"/api/projects/1/scopes/dev/{sample['dev_version']}/rows")
        assert branch_rows_response.status_code == 200
        assert scope_rows_response.status_code == 200

        branch_rows_payload = branch_rows_response.json()
        scope_rows_payload = scope_rows_response.json()
        assert branch_rows_payload["branch_ref"] == f"dev/{sample['dev_version']}"
        assert "scope_ref" not in branch_rows_payload
        assert scope_rows_payload["scope_ref"] == f"dev/{sample['dev_version']}"
        assert branch_rows_payload["rows"] == scope_rows_payload["rows"]

        branch_lookup_response = client.get(
            f"/api/projects/1/branches/dev/{sample['dev_version']}/lookup",
            params={"business_key": "dev.mutable"},
        )
        scope_lookup_response = client.get(
            f"/api/projects/1/scopes/dev/{sample['dev_version']}/lookup",
            params={"business_key": "dev.mutable"},
        )
        assert branch_lookup_response.status_code == 200
        assert scope_lookup_response.status_code == 200

        branch_lookup_payload = branch_lookup_response.json()
        scope_lookup_payload = scope_lookup_response.json()
        assert branch_lookup_payload["branch_ref"] == f"dev/{sample['dev_version']}"
        assert "scope_ref" not in branch_lookup_payload
        assert scope_lookup_payload["scope_ref"] == f"dev/{sample['dev_version']}"
        assert branch_lookup_payload["mode"] == scope_lookup_payload["mode"] == "business_key"
        assert branch_lookup_payload["value"] == scope_lookup_payload["value"] == "dev.mutable"
        assert branch_lookup_payload["rows"] == scope_lookup_payload["rows"]

        rel_branch_rows_response = client.get("/api/projects/1/branches/rel/current/rows")
        rel_scope_rows_response = client.get("/api/projects/1/scopes/rel/current/rows")
        assert rel_branch_rows_response.status_code == 200
        assert rel_scope_rows_response.status_code == 200
        assert rel_branch_rows_response.json()["branch_ref"] == "rel/current"
        assert rel_branch_rows_response.json()["rows"] == rel_scope_rows_response.json()["rows"]

        rel_branch_lookup_response = client.get(
            "/api/projects/1/branches/rel/current/lookup",
            params={"business_key": "common.welcome"},
        )
        rel_scope_lookup_response = client.get(
            "/api/projects/1/scopes/rel/current/lookup",
            params={"business_key": "common.welcome"},
        )
        assert rel_branch_lookup_response.status_code == 200
        assert rel_scope_lookup_response.status_code == 200
        assert rel_branch_lookup_response.json()["branch_ref"] == "rel/current"
        assert "scope_ref" not in rel_branch_lookup_response.json()
        assert rel_branch_lookup_response.json()["rows"] == rel_scope_lookup_response.json()["rows"]


def test_branch_first_routes_return_404_for_missing_project() -> None:
    reset_demo()

    with TestClient(app) as client:
        responses = [
            client.get("/api/projects/999/branches/rel/current/rows"),
            client.get("/api/projects/999/branches/rel/current/lookup", params={"business_key": "common.welcome"}),
        ]

    for response in responses:
        assert response.status_code == 404
        assert "project not found" in response.json()["detail"]


def test_branch_first_routes_reject_master_branch_refs() -> None:
    reset_demo()

    with TestClient(app) as client:
        rows_response = client.get("/api/projects/1/branches/master/rows")
        lookup_response = client.get(
            "/api/projects/1/branches/master/lookup",
            params={"business_key": "common.welcome"},
        )

    assert rows_response.status_code == 400
    assert lookup_response.status_code == 400
    assert "invalid" in rows_response.json()["detail"].lower()
    assert "invalid" in lookup_response.json()["detail"].lower()


def test_project_variants_route_returns_pivot_fields_and_supports_pivot_filters() -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Pivot Workspace Project",
        ["fr", "en", "de"],
        ["context"],
        "en",
        ["fr", "de"],
    )
    project_id = int(project["project_id"])
    catalog = VariantCatalogService()

    changed_by_dev = create_bound_variant(
        project_id=project_id,
        business_key="pivot.changed.dev",
        source="Hello",
        translations={"en": "Hello", "fr": "Bonjour", "de": "Hallo"},
        branch_refs=[BranchRef.dev("2.4.3"), BranchRef.rel_current()],
    )
    catalog.update_variant(
        changed_by_dev,
        catalog.build_content(
            "pivot.changed.dev.xlsx",
            "Hello",
            {"en": "Hello from dev", "fr": "Bonjour", "de": "Hallo"},
            {"context": "pivot.changed.dev"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )

    reviewed = create_bound_variant(
        project_id=project_id,
        business_key="pivot.reviewed.rel",
        source="Welcome",
        translations={"en": "Welcome", "fr": "Bienvenue", "de": "Willkommen"},
        branch_refs=[BranchRef.rel_current()],
    )
    catalog.update_variant(
        reviewed,
        catalog.build_content(
            "pivot.reviewed.rel.xlsx",
            "Welcome",
            {"en": "Welcome from rel", "fr": "Bienvenue", "de": "Willkommen"},
            {"context": "pivot.reviewed.rel"},
        ),
        actor_scope=BranchRef.rel_current().as_tuple(),
    )

    with TestClient(app) as client:
        review_response = client.post(
            f"/api/projects/{project_id}/variants/pivot/review",
            json={"branch_ref": "rel/current", "variant_ids": [reviewed]},
        )
        assert review_response.status_code == 200
        assert review_response.json()["job"]["status"] == "success"

        all_response = client.get(
            f"/api/projects/{project_id}/variants",
            params={"state": "all"},
        )
        assert all_response.status_code == 200
        payload = all_response.json()
        rows_by_key = {row["business_key"]: row for row in payload["rows"]}

        changed_row = rows_by_key["pivot.changed.dev"]
        assert changed_row["pivot_status"] == "changed"
        assert changed_row["pivot_changed_by_branch_ref"] == "dev/2.4.3"
        assert changed_row["pivot_changed_at"] is not None
        assert changed_row["pivot_reviewed_at"] is None

        reviewed_row = rows_by_key["pivot.reviewed.rel"]
        assert reviewed_row["pivot_status"] == "reviewed"
        assert reviewed_row["pivot_changed_by_branch_ref"] is None
        assert reviewed_row["pivot_changed_at"] is not None
        assert reviewed_row["pivot_reviewed_at"] is not None

        changed_filter = client.get(
            f"/api/projects/{project_id}/variants",
            params={"state": "all", "pivot_status": "changed"},
        )
        assert changed_filter.status_code == 200
        assert [row["business_key"] for row in changed_filter.json()["rows"]] == [
            "pivot.changed.dev"
        ]

        owner_filter = client.get(
            f"/api/projects/{project_id}/variants",
            params={
                "state": "all",
                "pivot_status": "changed",
                "pivot_changed_by_branch_ref": "dev/2.4.3",
                "branch_ref": "dev/2.4.3",
            },
        )
        assert owner_filter.status_code == 200
        assert [row["business_key"] for row in owner_filter.json()["rows"]] == [
            "pivot.changed.dev"
        ]


def test_project_variants_query_rows_match_variant_hydration_contract() -> None:
    reset_demo()
    rows = ReadModelRepository().list_live_variant_rows(
        1,
        VariantFilter(state="all"),
        page=1,
        page_size=5,
    )["rows"]

    assert rows
    required_columns = {
        "variant_id",
        "entry_id",
        "file_name",
        "source",
        "orphaned_at",
        "trashed_at",
        "trash_until",
        "restored_at",
        "pivot_status",
        "pivot_changed_by_scope_type",
        "pivot_changed_by_scope_value",
        "pivot_changed_at",
        "pivot_reviewed_at",
        "pivot_status_updated_at",
        "created_at",
        "updated_at",
    }
    assert required_columns.issubset(rows[0].keys())
    assert "variant_created_at" not in rows[0]
    assert "variant_updated_at" not in rows[0]


def test_entry_variants_route_returns_pivot_metadata() -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Pivot Inspection Project",
        ["fr", "en"],
        ["context"],
        "en",
        ["fr"],
    )
    project_id = int(project["project_id"])
    catalog = VariantCatalogService()
    variant_id = create_bound_variant(
        project_id=project_id,
        business_key="pivot.timeline",
        source="Hello",
        translations={"en": "Hello", "fr": "Bonjour"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )
    catalog.update_variant(
        variant_id,
        catalog.build_content(
            "pivot.timeline.xlsx",
            "Hello",
            {"en": "Hello from dev", "fr": "Bonjour"},
            {"context": "pivot.timeline"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )

    with TestClient(app) as client:
        response = client.get(
            f"/api/projects/{project_id}/entries/pivot.timeline/variants"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["business_key"] == "pivot.timeline"
    assert payload["variants"][0]["pivot_status"] == "changed"
    assert payload["variants"][0]["pivot_changed_by_branch_ref"] == "dev/2.4.3"
    assert payload["variants"][0]["pivot_changed_at"] is not None
    assert payload["variants"][0]["pivot_reviewed_at"] is None


def test_pivot_review_route_returns_job_detail_and_report_rows() -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Pivot Review API Project",
        ["fr", "en"],
        ["context"],
        "en",
        ["fr"],
    )
    project_id = int(project["project_id"])
    catalog = VariantCatalogService()

    reviewable = create_bound_variant(
        project_id=project_id,
        business_key="pivot.reviewable",
        source="Hello",
        translations={"en": "Hello", "fr": "Bonjour"},
        branch_refs=[BranchRef.dev("2.4.3"), BranchRef.rel_current()],
    )
    catalog.update_variant(
        reviewable,
        catalog.build_content(
            "pivot.reviewable.xlsx",
            "Hello",
            {"en": "Hello from dev", "fr": "Bonjour"},
            {"context": "pivot.reviewable"},
        ),
        actor_scope=BranchRef.dev("2.4.3").as_tuple(),
    )

    unchanged = create_bound_variant(
        project_id=project_id,
        business_key="pivot.init-only",
        source="Init",
        translations={"en": "Init", "fr": "Init"},
        branch_refs=[BranchRef.rel_current()],
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/projects/{project_id}/variants/pivot/review",
            json={
                "branch_ref": "rel/current",
                "variant_ids": [reviewable, unchanged, 999999],
            },
        )
        assert response.status_code == 200
        detail = response.json()

        assert detail["job"]["status"] == "success"
        assert detail["job"]["job_type"] == "pivot_review"
        assert detail["job"]["summary"]["reviewed_count"] == 1
        assert detail["job"]["summary"]["not_changed_count"] == 1
        assert detail["job"]["summary"]["missing_count"] == 1

        statuses = {
            row["variant_id"]: row["status"]
            for row in detail["report"]["rows"]
        }
        assert statuses == {
            reviewable: "REVIEWED",
            unchanged: "NOT_CHANGED",
            999999: "MISSING",
        }

        variants_response = client.get(
            f"/api/projects/{project_id}/variants",
            params={"state": "all", "pivot_status": "reviewed"},
        )
        assert variants_response.status_code == 200
        rows = variants_response.json()["rows"]
        assert [row["business_key"] for row in rows] == ["pivot.reviewable"]
        assert rows[0]["pivot_changed_by_branch_ref"] is None
        assert rows[0]["pivot_reviewed_at"] is not None


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


def test_project_trash_route_trashes_orphan_variants() -> None:
    reset_demo()
    with TestClient(app) as client:
        delete_response = client.post(
            "/api/projects/1/variants/trash/delete",
            json={"branch_ref": "rel/current", "business_keys": ["common.welcome"]},
        )
        assert delete_response.status_code == 200
        delete_detail = wait_for_job(client, delete_response.json())
        assert delete_detail["job"]["status"] == "success"

        trash_response = client.post(
            "/api/projects/1/variants/trash",
            json={"business_keys": ["common.welcome"]},
        )
        assert trash_response.status_code == 200
        trash_detail = wait_for_job(client, trash_response.json())
        assert trash_detail["job"]["status"] == "success"
        assert trash_detail["report"]["summary"]["trashed_count"] == 1


def test_same_source_candidates_exclude_trashed_variants() -> None:
    reset_demo()
    variant_service = TrashRestoreService()

    variant_service.delete(BranchRef.rel_current(), ["common.welcome"])
    variant_service.project_trash(["common.welcome"])

    with TestClient(app) as client:
        response = client.get(
            "/api/projects/1/history/same-source-candidates",
            params={"business_key": "common.welcome", "source": "Welcome {0}"},
        )
        assert response.status_code == 200
        rows = response.json()["rows"]
        assert all(row["state"] != "trashed" for row in rows)


def test_entry_timeline_excludes_trashed_variants() -> None:
    reset_demo()
    variant_service = TrashRestoreService()

    variant_service.delete(BranchRef.rel_current(), ["common.welcome"])
    variant_service.project_trash(["common.welcome"])

    with TestClient(app) as client:
        response = client.get("/api/projects/1/entries/common.welcome/variants")
        assert response.status_code == 200
        variants = response.json()["variants"]
        assert all(v["is_trashed"] is False for v in variants)
