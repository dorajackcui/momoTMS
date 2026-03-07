from app.main import app
from app.services.demo.service import DemoService
from app.services.imports.service import ImportService
from app.services.project.service import ProjectService
from app.services.shared.io import normalize_non_content_value
from app.services.shared.jobs import JobService
from app.services.shared.utils import now_iso
from app.services.variant.compatibility import StringService
from app.services.variant.facade import VariantService
from app.services.variant.records import EntryRecord
from app.services.variant.repositories import VariantRepository
from app.services.variant.services import EntryService
from app.services.workflows.dev_versions import DevVersionService
from app.services.workflows.promote import PromoteService
from app.services.workflows.qa import QaScanService
from app.services.workflows.qa_rules import validate_pair
from app.services.workflows.rel import RelService
from app.services.workflows.trash import TrashService
from app.services.workflows.workbench import WorkbenchService


def test_new_service_paths_import_and_expose_expected_symbols() -> None:
    assert callable(now_iso)
    assert normalize_non_content_value(" x ") == "x"
    assert DemoService is not None
    assert ProjectService is not None
    assert VariantService is not None
    assert StringService is not None
    assert EntryService is not None
    assert VariantRepository is not None
    assert ImportService is not None
    assert DevVersionService is not None
    assert PromoteService is not None
    assert RelService is not None
    assert TrashService is not None
    assert QaScanService is not None
    assert WorkbenchService is not None
    assert JobService is not None
    assert EntryRecord is not None
    assert callable(validate_pair)


def test_app_still_registers_main_routes_after_service_cleanup() -> None:
    paths = {route.path for route in app.routes}
    assert "/api/projects" in paths
    assert "/api/projects/{project_id}/imports/upload-folder" in paths
    assert "/api/projects/{project_id}/dev-versions/import" in paths
    assert "/api/projects/{project_id}/scopes/compare" in paths
    assert "/api/projects/{project_id}/jobs/{job_id}" in paths
