from pathlib import Path

from app.db import DB_PATH
from app.services.demo_service import DemoService
from app.services.workbench_service import WorkbenchService


def reset_demo() -> dict:
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
    demo = DemoService()
    demo.reset()
    return demo.get_sample("core-cycle")


def test_workbench_runs_import_dev_fill_and_qa_jobs() -> None:
    sample = reset_demo()
    workbench = WorkbenchService()

    state = workbench.get_state()
    assert state["rel_summary"]["count"] == 5
    assert state["trash_count"] == 0

    import_job = workbench.import_directory(sample["paths"]["import_dir"])
    assert import_job["job"]["job_type"] == "import_directory"
    batch_id = import_job["job"]["summary"]["import_batch_id"]

    dev_job = workbench.dev_import(batch_id, sample["dev_version"])
    assert dev_job["job"]["job_type"] == "dev_import"
    assert dev_job["job"]["summary"]["processed_count"] == 4

    fill_job = workbench.fill(sample["paths"]["fill_dir"], sample["lang"])
    assert fill_job["job"]["job_type"] == "fill_export"
    assert fill_job["job"]["artifact_path"].endswith("filled_export.zip")

    qa_job = workbench.qa(sample["paths"]["fill_dir"], sample["lang"])
    assert qa_job["job"]["job_type"] == "qa_report"
    assert qa_job["job"]["summary"]["issue_count"] >= 1
