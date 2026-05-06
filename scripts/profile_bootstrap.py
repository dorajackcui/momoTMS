"""Profile create-dev-branch (bootstrap) pipeline, stage by stage."""
from __future__ import annotations

import shutil
import sys
import tempfile
import argparse
import os
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import init_db
from app.services.project.service import ProjectService
from app.services.branch.models import BranchRef
from app.services.branch.bootstrap import BranchBootstrapService
from app.services.workbooks.batches import WorkbookBatchService
from app.services.workbooks.models import WorkbookWorkflowContext


def log(msg: str) -> None:
    print(msg, flush=True)


def find_project(name: str) -> int:
    for p in ProjectService().list_projects():
        if p["name"] == name:
            return int(p["project_id"])
    raise KeyError(f"project not found: {name}")


def run(excel_path: str, project_name: str, branch_name: str) -> None:
    init_db()
    project_id = find_project(project_name)
    log(f"project_id={project_id}  branch={branch_name}")

    t0 = perf_counter()
    tmp = Path(tempfile.mkdtemp(prefix="bootstrap_profile_"))
    shutil.copy2(excel_path, tmp / Path(excel_path).name)
    log(f"[stage 0] copy file  ({perf_counter()-t0:.2f}s)")

    t1 = perf_counter()
    context = WorkbookWorkflowContext(workflow_kind="create_branch")
    batch = WorkbookBatchService().create_batch_from_directory(tmp, project_id, context)
    batch_id = int(batch["import_batch_id"])
    log(f"[stage 1] parse Excel + write import_rows: "
        f"{batch['rows_scanned']} rows, {batch['issues']} issues  ({perf_counter()-t1:.2f}s)")

    t2 = perf_counter()
    branch_ref = BranchRef.parse(branch_name)
    result = BranchBootstrapService().bootstrap(branch_ref, batch_id, project_id=project_id)
    summary = result["summary"]
    log(f"[stage 2] bootstrap  ({perf_counter()-t2:.2f}s)")
    log(f"  bound_existing:    {summary['bound_existing_variant_count']}")
    log(f"  created_and_bound: {summary['created_and_bound_variant_count']}")
    log(f"  created_entries:   {summary['created_entry_count']}")
    log(f"  invalid_rows:      {summary['invalid_row_count']}")
    log(f"  duplicate_keys:    {summary['duplicate_key_count']}")
    for stage in summary.get("stages", []):
        log(f"  stage '{stage['stage']}': {stage['elapsed_ms']}ms  {stage.get('meta', '')}")

    log(f"\n[TOTAL] {perf_counter()-t0:.2f}s")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profile create-dev-branch bootstrap against a local workbook.")
    parser.add_argument(
        "--workbook",
        default=os.getenv("MOMO_TMS_BOOTSTRAP_PROFILE_WORKBOOK"),
        help="Workbook path, or set MOMO_TMS_BOOTSTRAP_PROFILE_WORKBOOK.",
    )
    parser.add_argument("--project-name", default="seed_test")
    parser.add_argument("--branch", default="dev/2.5.7")
    args = parser.parse_args()
    if not args.workbook:
        raise SystemExit("Pass --workbook or set MOMO_TMS_BOOTSTRAP_PROFILE_WORKBOOK.")
    run(args.workbook, project_name=args.project_name, branch_name=args.branch)
