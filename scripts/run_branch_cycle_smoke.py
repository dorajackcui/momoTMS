#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from time import perf_counter
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_ROOT = ROOT / "data" / "branch_cycle_smoke_inputs"
DEFAULT_RELEASE_WORKBOOK = Path(
    os.getenv("MOMO_TMS_RELEASE_WORKBOOK") or DEFAULT_INPUT_ROOT / "2.4diff3.xlsx"
)
DEFAULT_DEV_WORKBOOK = Path(
    os.getenv("MOMO_TMS_DEV_WORKBOOK") or DEFAULT_INPUT_ROOT / "2.5diff3.xlsx"
)
DEFAULT_RUNTIME_ROOT = ROOT / "data" / "branch_cycle_smoke"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the focused branch-cycle smoke flow against local Excel workbooks.",
    )
    parser.add_argument(
        "--release-workbook",
        type=Path,
        default=DEFAULT_RELEASE_WORKBOOK,
        help="2.4 release workbook path. Defaults to MOMO_TMS_RELEASE_WORKBOOK or data/branch_cycle_smoke_inputs/2.4diff3.xlsx.",
    )
    parser.add_argument(
        "--dev-workbook",
        type=Path,
        default=DEFAULT_DEV_WORKBOOK,
        help="2.5 dev workbook path. Defaults to MOMO_TMS_DEV_WORKBOOK or data/branch_cycle_smoke_inputs/2.5diff3.xlsx.",
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=DEFAULT_RUNTIME_ROOT,
        help="Isolated runtime directory for DB, jobs, and staged workbook copies.",
    )
    parser.add_argument(
        "--project-name",
        default="branch-cycle-smoke",
        help="Project name to create in the isolated runtime.",
    )
    parser.add_argument(
        "--dev-version",
        default="2.5.3",
        help="Dev branch version to create, e.g. 2.5.3.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=5000,
        help="Bulk seed chunk size.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the runtime root first. Only repo data/ children are allowed.",
    )
    parser.add_argument(
        "--stop-after",
        choices=[
            "project",
            "release-seed",
            "bootstrap-batch",
            "bootstrap",
            "content-batch",
            "content-mutation",
        ],
        help="Stop after the named checkpoint.",
    )
    parser.add_argument(
        "--content-progress-interval",
        type=int,
        default=1000,
        help="Print content mutation progress every N rows. Use 0 to disable.",
    )
    parser.add_argument(
        "--max-content-seconds",
        type=float,
        default=300.0,
        help="Abort content mutation after this many seconds. Use 0 to disable.",
    )
    args = parser.parse_args()

    try:
        run(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def run(args: argparse.Namespace) -> None:
    release_workbook = args.release_workbook.resolve()
    dev_workbook = args.dev_workbook.resolve()
    if not release_workbook.exists():
        raise FileNotFoundError(f"release workbook not found: {release_workbook}")
    if not dev_workbook.exists():
        raise FileNotFoundError(f"dev workbook not found: {dev_workbook}")

    runtime_root = args.runtime_root.resolve()
    configure_runtime(runtime_root, reset=bool(args.reset))

    sys.path.insert(0, str(ROOT))
    from app.db import get_conn, init_db
    from app.services.branch.bootstrap import BranchBootstrapService
    from app.services.branch.models import BranchRef
    from app.services.branch.mutations import BranchMutationService
    from app.services.bulk.writer import BulkVariantWriter
    from app.services.project.service import ProjectService
    from app.services.workbooks.batches import WorkbookBatchService
    from app.services.workbooks.models import WorkbookWorkflowContext

    init_db()
    try:
        with StepTimer("create project"):
            project = ProjectService().create_project(
                args.project_name,
                ["en", "fr", "es"],
                ["Version", "SpeakerName"],
                pivot_language="en",
                pivoted_languages=["fr", "es"],
                business_key_header="Key",
                source_header="MsgStr",
            )
    except ValueError as exc:
        raise ValueError(f"{exc}; rerun with --reset or choose a different --project-name") from exc
    project_id = int(project["project_id"])
    log(f"project_id={project_id} name={project['name']}")
    log(f"runtime_root={runtime_root}")
    stop_if_requested(args, "project")

    with StepTimer("release bulk seed"):
        release_summary = BulkVariantWriter().seed(
            project_id=project_id,
            branch_ref=BranchRef.rel_current(),
            workbook_path=str(release_workbook),
            chunk_size=int(args.chunk_size),
        )
    print_summary("release bulk seed", release_summary)
    stop_if_requested(args, "release-seed")

    dev_ref = BranchRef.dev(args.dev_version)
    with StepTimer("copy dev workbook for bootstrap"):
        bootstrap_dir = copy_single_workbook(
            dev_workbook,
            runtime_root / "inputs" / "dev-bootstrap",
        )
    with StepTimer("bootstrap workbook batch"):
        bootstrap_batch = WorkbookBatchService().create_batch_from_directory(
            bootstrap_dir,
            project_id,
            WorkbookWorkflowContext(workflow_kind="create_branch"),
        )
    print_summary("dev workbook batch", bootstrap_batch)
    stop_if_requested(args, "bootstrap-batch")

    with StepTimer("dev branch bootstrap"):
        bootstrap = BranchBootstrapService().bootstrap(
            dev_ref,
            bootstrap_batch["workbook_batch_id"],
            project_id=project_id,
        )
    print_summary("dev branch bootstrap", bootstrap["summary"])
    stop_if_requested(args, "bootstrap")

    with StepTimer("copy dev workbook for content mutation"):
        content_dir = copy_single_workbook(
            dev_workbook,
            runtime_root / "inputs" / "dev-content",
        )
    with StepTimer("content mutation workbook batch"):
        content_batch = WorkbookBatchService().create_batch_from_directory(
            content_dir,
            project_id,
            WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
        )
    print_summary("content workbook batch", content_batch)
    stop_if_requested(args, "content-batch")

    max_content_seconds = float(args.max_content_seconds)
    max_content_seconds = None if max_content_seconds <= 0 else max_content_seconds
    with StepTimer("dev content mutation"):
        mutation_service = BranchMutationService()
        with get_conn() as conn:
            mutation = mutation_service.content_batch.apply(
                dev_ref,
                int(content_batch["workbook_batch_id"]),
                project_id,
                conn=conn,
                progress_callback=lambda payload: print_summary("dev content mutation progress", payload),
                progress_interval=max(0, int(args.content_progress_interval)),
                max_elapsed_seconds=max_content_seconds,
            )
    print_summary("dev content mutation", mutation["summary"])
    stop_if_requested(args, "content-mutation")


def configure_runtime(runtime_root: Path, *, reset: bool) -> None:
    if reset and runtime_root.exists():
        data_root = (ROOT / "data").resolve()
        if runtime_root == data_root:
            raise ValueError("--reset refuses to remove the repo data/ directory itself")
        if data_root not in runtime_root.parents:
            raise ValueError("--reset only removes runtime roots under the repo data/ directory")
        shutil.rmtree(runtime_root)

    jobs_dir = runtime_root / "jobs"
    demo_root = runtime_root / "demo_samples"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    demo_root.mkdir(parents=True, exist_ok=True)
    os.environ["MOMO_TMS_DB_PATH"] = str(runtime_root / "tms.db")
    os.environ["MOMO_TMS_JOBS_DIR"] = str(jobs_dir)
    os.environ["MOMO_TMS_DEMO_ROOT"] = str(demo_root)


def copy_single_workbook(source: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    for old_workbook in target_dir.glob("*.xlsx"):
        old_workbook.unlink()
    target = target_dir / source.name
    shutil.copy2(source, target)
    return target_dir


class StepTimer:
    def __init__(self, label: str) -> None:
        self.label = label
        self.started = 0.0

    def __enter__(self) -> StepTimer:
        self.started = perf_counter()
        log(f"\n>>> START {self.label}")
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        elapsed = perf_counter() - self.started
        status = "FAIL" if exc_type else "END"
        log(f"<<< {status} {self.label}: {elapsed:.2f}s")


def stop_if_requested(args: argparse.Namespace, checkpoint: str) -> None:
    if args.stop_after == checkpoint:
        log(f"\nStopped after checkpoint: {checkpoint}")
        raise SystemExit(0)


def log(message: str) -> None:
    print(message, flush=True)


def print_summary(label: str, summary: dict[str, Any]) -> None:
    interesting_keys = [
        "entries_created",
        "variants_created",
        "bindings_created",
        "rows_scanned",
        "issues",
        "processed_count",
        "bound_existing_variant_count",
        "created_and_bound_variant_count",
        "updated_bound_variant_count",
        "noop_count",
        "content_filtered_by_authority_count",
        "invalid_row_count",
        "duplicate_key_count",
        "created_entry_count",
        "created_variant_count",
        "elapsed_ms",
    ]
    log(f"\n[{label}]")
    for key in interesting_keys:
        if key in summary:
            log(f"  {key}: {summary[key]}")
    for stage in summary.get("stages", []):
        if isinstance(stage, dict):
            stage_name = stage.get("stage", "unknown")
            elapsed_ms = stage.get("elapsed_ms")
            meta = stage.get("meta", {})
            log(f"  stage.{stage_name}.elapsed_ms: {elapsed_ms}")
            if meta:
                log(f"  stage.{stage_name}.meta: {meta}")


if __name__ == "__main__":
    raise SystemExit(main())
