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


def build_parser() -> argparse.ArgumentParser:
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
        "--next-dev-workbook",
        type=Path,
        help="Second dev workbook path. Defaults to --dev-workbook when omitted.",
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
        "--next-dev-version",
        default="2.5.4",
        help="Second dev branch version to create before replacing rel/current.",
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
            "next-bootstrap-batch",
            "next-bootstrap",
            "next-content-batch",
            "next-content-mutation",
            "replace-current-rel",
        ],
        help="Stop after the named checkpoint.",
    )
    parser.add_argument(
        "--content-progress-interval",
        type=int,
        default=5000,
        help="Print content mutation progress every N rows. Defaults to 5000. Use 0 to disable.",
    )
    parser.add_argument(
        "--max-content-seconds",
        type=float,
        default=300.0,
        help="Abort content mutation after this many seconds. Use 0 to disable.",
    )
    return parser


def main() -> int:
    parser = build_parser()
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
    next_dev_workbook = (getattr(args, "next_dev_workbook", None) or args.dev_workbook).resolve()
    if not release_workbook.exists():
        raise FileNotFoundError(f"release workbook not found: {release_workbook}")
    if not dev_workbook.exists():
        raise FileNotFoundError(f"dev workbook not found: {dev_workbook}")
    if not next_dev_workbook.exists():
        raise FileNotFoundError(f"next dev workbook not found: {next_dev_workbook}")

    runtime_root = args.runtime_root.resolve()
    configure_runtime(runtime_root, reset=bool(args.reset))

    sys.path.insert(0, str(ROOT))
    from app.db import get_conn, init_db
    from app.services.branch.bootstrap import BranchBootstrapService
    from app.services.branch.models import BranchRef
    from app.services.branch.mutations import BranchMutationService
    from app.services.branch.replace import BranchReplaceService
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

    workbook_batch_service = WorkbookBatchService()
    bootstrap_service = BranchBootstrapService()
    mutation_service = BranchMutationService()

    dev_ref = BranchRef.dev(args.dev_version)
    run_dev_cycle(
        branch_ref=dev_ref,
        workbook=dev_workbook,
        project_id=project_id,
        runtime_root=runtime_root,
        input_slug="dev",
        args=args,
        bootstrap_batch_checkpoint="bootstrap-batch",
        bootstrap_checkpoint="bootstrap",
        content_batch_checkpoint="content-batch",
        content_mutation_checkpoint="content-mutation",
        workbook_batch_service=workbook_batch_service,
        bootstrap_service=bootstrap_service,
        mutation_service=mutation_service,
        workbook_context_type=WorkbookWorkflowContext,
        get_conn_fn=get_conn,
    )

    next_dev_ref = BranchRef.dev(getattr(args, "next_dev_version", None) or "2.5.4")
    run_dev_cycle(
        branch_ref=next_dev_ref,
        workbook=next_dev_workbook,
        project_id=project_id,
        runtime_root=runtime_root,
        input_slug="next-dev",
        args=args,
        bootstrap_batch_checkpoint="next-bootstrap-batch",
        bootstrap_checkpoint="next-bootstrap",
        content_batch_checkpoint="next-content-batch",
        content_mutation_checkpoint="next-content-mutation",
        workbook_batch_service=workbook_batch_service,
        bootstrap_service=bootstrap_service,
        mutation_service=mutation_service,
        workbook_context_type=WorkbookWorkflowContext,
        get_conn_fn=get_conn,
    )

    with StepTimer(f"replace {next_dev_ref} -> rel/current"):
        replace = BranchReplaceService().execute(
            next_dev_ref,
            BranchRef.rel_current(),
            project_id=project_id,
        )
    print_summary(f"replace {next_dev_ref} -> rel/current", replace["summary"])
    stop_if_requested(args, "replace-current-rel")


def run_dev_cycle(
    *,
    branch_ref: Any,
    workbook: Path,
    project_id: int,
    runtime_root: Path,
    input_slug: str,
    args: argparse.Namespace,
    bootstrap_batch_checkpoint: str,
    bootstrap_checkpoint: str,
    content_batch_checkpoint: str,
    content_mutation_checkpoint: str,
    workbook_batch_service: Any,
    bootstrap_service: Any,
    mutation_service: Any,
    workbook_context_type: Any,
    get_conn_fn: Any,
) -> None:
    branch_label = str(branch_ref)
    with StepTimer(f"copy {branch_label} workbook for bootstrap"):
        bootstrap_dir = copy_single_workbook(
            workbook,
            runtime_root / "inputs" / f"{input_slug}-bootstrap",
        )
    with StepTimer(f"{branch_label} bootstrap workbook batch"):
        bootstrap_batch = workbook_batch_service.create_batch_from_directory(
            bootstrap_dir,
            project_id,
            workbook_context_type(workflow_kind="create_branch"),
        )
    print_summary(f"{branch_label} workbook batch", bootstrap_batch)
    stop_if_requested(args, bootstrap_batch_checkpoint)

    with StepTimer(f"{branch_label} branch bootstrap"):
        bootstrap = bootstrap_service.bootstrap(
            branch_ref,
            bootstrap_batch["workbook_batch_id"],
            project_id=project_id,
        )
    print_summary(f"{branch_label} branch bootstrap", bootstrap["summary"])
    stop_if_requested(args, bootstrap_checkpoint)

    with StepTimer(f"copy {branch_label} workbook for content mutation"):
        content_dir = copy_single_workbook(
            workbook,
            runtime_root / "inputs" / f"{input_slug}-content",
        )
    with StepTimer(f"{branch_label} content mutation workbook batch"):
        content_batch = workbook_batch_service.create_batch_from_directory(
            content_dir,
            project_id,
            workbook_context_type(workflow_kind="branch_mutation", mutation_type="content"),
        )
    print_summary(f"{branch_label} content workbook batch", content_batch)
    stop_if_requested(args, content_batch_checkpoint)

    max_content_seconds = float(args.max_content_seconds)
    max_content_seconds = None if max_content_seconds <= 0 else max_content_seconds
    with StepTimer(f"{branch_label} content mutation"):
        with get_conn_fn() as conn:
            mutation = mutation_service.content_batch.apply(
                branch_ref,
                int(content_batch["workbook_batch_id"]),
                project_id,
                conn=conn,
                progress_callback=lambda payload: print_summary(
                    f"{branch_label} content mutation progress",
                    payload,
                ),
                progress_interval=max(0, int(args.content_progress_interval)),
                max_elapsed_seconds=max_content_seconds,
            )
    print_summary(f"{branch_label} content mutation", mutation["summary"])
    stop_if_requested(args, content_mutation_checkpoint)


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
