from io import BytesIO
from pathlib import Path
import time

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.db import get_db_path
from app.main import app
from app.services.branch.models import BranchRef
from app.services.demo.service import DemoService
from app.services.imports.service import ImportService
from app.services.project.service import ProjectService
from app.services.read_models.variants import ProjectVariantsQueryRepository
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
        bindings.bind_scope(int(entry["entry_id"]), branch_ref, variant_id)
    return variant_id


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
            client.get("/api/projects/999/variants"),
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
    services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.rel_current(), variant_id)

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
    services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.dev("2.4.3"), int(variant["variant_id"]))

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
    services.bindings.bind_scope(int(entry["entry_id"]), BranchRef.rel_current(), int(variant["variant_id"]))
    trash_restore.delete(BranchRef.rel_current(), ["trash.me"])

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
                    "mark_as_candidate_release": True,
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
    rows = ProjectVariantsQueryRepository().list_variant_rows(
        1,
        state="all",
        branch_refs=[],
        search_business_key=None,
        search_source=None,
        pivot_status=None,
        pivot_changed_by_branch_ref=None,
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
