from pathlib import Path

from app.db import DB_PATH
from app.services.branch_service import BranchService
from app.services.demo_service import DemoService
from app.services.workbench_service import WorkbenchService


def test_workbench_update_dev_and_promote_create_jobs_and_move_branch_head() -> None:
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()

    DemoService().reset()
    branches = BranchService()
    workbench = WorkbenchService()

    original_release = branches.get_head("release")

    update_job = workbench.update_dev("core-cycle")
    assert update_job["job"]["status"] == "success"
    assert update_job["job"]["job_type"] == "update_dev"
    assert branches.get_head("dev") == update_job["job"]["snapshot_id"]

    preview = workbench.preview_promote("2.4.0")
    assert preview["added_count"] == 3
    assert preview["conflict_src_changed_count"] == 1
    assert preview["carried_over_count"] == 2
    assert preview["deprecated_count"] == 3

    promote_job = workbench.execute_promote("2.4.0")
    assert promote_job["job"]["status"] == "success"
    assert promote_job["job"]["job_type"] == "promote_execute"
    assert promote_job["job"]["snapshot_id"] != original_release
    assert branches.get_head("release") == promote_job["job"]["snapshot_id"]
