from app.main import app
from app.services.branch import BranchKind, BranchMutationService, BranchRef, BranchReplaceService, BranchService
from app.services.demo.service import DemoService
from app.services.imports.service import ImportService
from app.services.project.service import ProjectService
from app.services.shared.io import normalize_non_content_value
from app.services.shared.jobs import JobService
from app.services.shared.utils import now_iso
from app.services.variant.records import EntryVariantView
from app.services.variant.repositories import VariantRepository
from app.services.variant.services import EntryService, EntryVariantViewAssembler
from app.services.variant.workflows import VariantWorkflowService
from app.services.workflows.fill import FillService
from app.services.workflows.qa import QaScanService
from app.services.workflows.workbench import WorkflowService


def test_new_service_paths_import_and_expose_expected_symbols() -> None:
    assert callable(now_iso)
    assert normalize_non_content_value(" x ") == "x"
    assert DemoService is not None
    assert ProjectService is not None
    assert BranchService is not None
    assert BranchMutationService is not None
    assert BranchReplaceService is not None
    assert BranchRef is not None
    assert BranchKind is not None
    assert EntryService is not None
    assert EntryVariantViewAssembler is not None
    assert VariantRepository is not None
    assert ImportService is not None
    assert FillService is not None
    assert QaScanService is not None
    assert WorkflowService is not None
    assert JobService is not None
    assert EntryVariantView is not None
    assert VariantWorkflowService is not None


def test_app_registers_branch_centric_routes_only() -> None:
    paths = {route.path for route in app.routes}
    assert "/api/projects" in paths
    assert "/api/projects/{project_id}/state" in paths
    assert "/api/projects/{project_id}/imports/upload-folder" in paths
    assert "/api/projects/{project_id}/branches" in paths
    assert "/api/projects/{project_id}/branches/compare" in paths
    assert "/api/projects/{project_id}/branches/mutations" in paths
    assert "/api/projects/{project_id}/branches/replace/execute" in paths
    assert "/api/projects/{project_id}/jobs/{job_id}" in paths
    assert "/variant-workbench" in paths
    assert "/api/state" not in paths
    assert "/api/strings" not in paths
    assert "/api/dev-versions/import" not in paths
    assert "/api/scopes/compare" not in paths
    assert "/api/projects/{project_id}/branches/dev/import" not in paths
