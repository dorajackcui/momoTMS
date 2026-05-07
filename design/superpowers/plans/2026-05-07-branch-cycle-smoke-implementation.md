# Branch Cycle Smoke Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand `scripts/run_branch_cycle_smoke.py` to run two dev branch bootstrap/content cycles and then replace `rel/current` from the final dev branch.

**Architecture:** Keep the smoke runner as a single script but extract one local helper for the repeated dev branch cycle. Add optional CLI arguments for the second dev branch while preserving the existing command shape. Cover the flow with a small real-workbook pytest integration test and update the smoke guidance in `docs/testing.md`.

**Tech Stack:** Python, argparse, openpyxl test workbooks, pytest, existing Momo TMS branch services.

---

## File Structure

- Create `tests/test_branch_cycle_smoke_runner.py`: focused integration coverage for the smoke runner using tiny temporary workbooks and an isolated runtime root.
- Modify `scripts/run_branch_cycle_smoke.py`: add second-dev CLI arguments, extract repeated dev branch execution, execute final branch replace, and extend stop checkpoints.
- Modify `docs/testing.md`: update the local smoke runner guidance to mention two dev cycles, `--next-dev-version`, `--next-dev-workbook`, and the final replace.

### Task 1: Add Failing Smoke Runner Test

**Files:**
- Create: `tests/test_branch_cycle_smoke_runner.py`
- Read: `scripts/run_branch_cycle_smoke.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_branch_cycle_smoke_runner.py` with a real end-to-end script call:

```python
from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from openpyxl import Workbook

from app.services.branch.models import BranchRef
from app.services.read_models.derived.branch_catalog import BranchCatalogView
from scripts import run_branch_cycle_smoke


HEADERS = ["Key", "MsgStr", "en", "fr", "es", "Version", "SpeakerName"]


def write_workbook(path: Path, rows: list[list[object]]) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    workbook.close()
    return path


def rows_by_key(branch_ref: BranchRef, project_id: int) -> dict[str, dict]:
    return {
        row["business_key"]: row
        for row in BranchCatalogView().list_branch_entries(branch_ref, project_id=project_id)
    }


def test_smoke_runner_runs_two_dev_cycles_then_replaces_release(tmp_path, capsys) -> None:
    release_workbook = write_workbook(
        tmp_path / "release" / "2.4diff3.xlsx",
        [
            ["smoke.same", "Shared source", "Shared source", "FR rel same", "ES rel same", "2.4", "Rel"],
            ["smoke.changed", "Release source", "Release source", "FR rel changed", "ES rel changed", "2.4", "Rel"],
        ],
    )
    first_dev_workbook = write_workbook(
        tmp_path / "dev1" / "2.5diff3.xlsx",
        [
            ["smoke.same", "Shared source", "Blocked EN", "Blocked FR", "Blocked ES", "2.5", "Dev1"],
            ["smoke.changed", "First dev source", "First dev source", "FR dev first", "ES dev first", "2.5", "Dev1"],
            ["smoke.first-only", "First only source", "First only source", "FR first only", "ES first only", "2.5", "Dev1"],
        ],
    )
    second_dev_workbook = write_workbook(
        tmp_path / "dev2" / "2.5-next.xlsx",
        [
            ["smoke.same", "Shared source", "Blocked EN 2", "Blocked FR 2", "Blocked ES 2", "2.5", "Dev2"],
            ["smoke.changed", "Second dev source", "Second dev source", "FR dev second", "ES dev second", "2.5", "Dev2"],
            ["smoke.next-only", "Next only source", "Next only source", "FR next only", "ES next only", "2.5", "Dev2"],
        ],
    )

    args = Namespace(
        release_workbook=release_workbook,
        dev_workbook=first_dev_workbook,
        next_dev_workbook=second_dev_workbook,
        runtime_root=tmp_path / "runtime",
        project_name="branch-cycle-smoke-test",
        dev_version="2.5.3",
        next_dev_version="2.5.4",
        chunk_size=100,
        reset=False,
        stop_after=None,
        content_progress_interval=0,
        max_content_seconds=30,
    )

    run_branch_cycle_smoke.run(args)

    output = capsys.readouterr().out
    assert "dev/2.5.3 content mutation" in output
    assert "dev/2.5.4 content mutation" in output
    assert "replace dev/2.5.4 -> rel/current" in output

    rel_rows = rows_by_key(BranchRef.rel_current(), project_id=1)
    assert set(rel_rows) == {"smoke.same", "smoke.changed", "smoke.next-only"}
    assert rel_rows["smoke.same"]["source"] == "Shared source"
    assert rel_rows["smoke.same"]["translations"]["fr"] == "FR rel same"
    assert rel_rows["smoke.changed"]["source"] == "Second dev source"
    assert rel_rows["smoke.changed"]["translations"]["fr"] == "FR dev second"
    assert rel_rows["smoke.next-only"]["translations"]["es"] == "ES next only"
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_cycle_smoke_runner.py
```

Expected: FAIL because `Namespace` includes `next_dev_workbook` and `next_dev_version`, but the script does not use them yet, so output lacks `dev/2.5.4 content mutation` and final rel still reflects the old single-dev flow.

### Task 2: Implement Two Dev Cycles And Final Replace

**Files:**
- Modify: `scripts/run_branch_cycle_smoke.py`
- Test: `tests/test_branch_cycle_smoke_runner.py`

- [ ] **Step 1: Add CLI arguments and stop checkpoints**

In `scripts/run_branch_cycle_smoke.py`, add:

```python
    parser.add_argument(
        "--next-dev-workbook",
        type=Path,
        help="Second dev workbook path. Defaults to --dev-workbook when omitted.",
    )
    parser.add_argument(
        "--next-dev-version",
        default="2.5.4",
        help="Second dev branch version to create before replacing rel/current.",
    )
```

Extend `--stop-after` choices with:

```python
            "next-bootstrap-batch",
            "next-bootstrap",
            "next-content-batch",
            "next-content-mutation",
            "replace-current-rel",
```

- [ ] **Step 2: Resolve and validate the second workbook path**

Near existing workbook resolution:

```python
    next_dev_workbook = (args.next_dev_workbook or args.dev_workbook).resolve()
    if not next_dev_workbook.exists():
        raise FileNotFoundError(f"next dev workbook not found: {next_dev_workbook}")
```

- [ ] **Step 3: Import replace service**

Add:

```python
    from app.services.branch.replace import BranchReplaceService
```

- [ ] **Step 4: Extract a helper for one dev branch cycle**

Add a helper that copies the given workbook, creates bootstrap/content batches, applies bootstrap and content mutation, and honors prefix-specific stop checkpoints:

```python
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
```

- [ ] **Step 5: Replace the duplicated inline dev flow**

In `run()`, instantiate shared services and call:

```python
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

    next_dev_ref = BranchRef.dev(args.next_dev_version)
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
```

- [ ] **Step 6: Execute final replace**

After the second dev cycle:

```python
    with StepTimer(f"replace {next_dev_ref} -> rel/current"):
        replace = BranchReplaceService().execute(
            next_dev_ref,
            BranchRef.rel_current(),
            project_id=project_id,
        )
    print_summary(f"replace {next_dev_ref} -> rel/current", replace["summary"])
    stop_if_requested(args, "replace-current-rel")
```

- [ ] **Step 7: Run the focused test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_branch_cycle_smoke_runner.py
```

Expected: PASS.

### Task 3: Update Smoke Runner Documentation

**Files:**
- Modify: `docs/testing.md`

- [ ] **Step 1: Update the smoke runner command guidance**

Revise the existing `scripts/run_branch_cycle_smoke.py` paragraph so it states that the runner now seeds release, creates and content-updates two dev branches, and replaces `rel/current` from the second branch. Include this command form:

```powershell
.\.venv\Scripts\python.exe scripts\run_branch_cycle_smoke.py --reset --release-workbook <path-to-release.xlsx> --dev-workbook <path-to-first-dev.xlsx> --next-dev-workbook <path-to-second-dev.xlsx>
```

Also document that `--next-dev-workbook` is optional and defaults to `--dev-workbook`, while `--next-dev-version` defaults to `2.5.4`.

- [ ] **Step 2: Mention new stop-after checkpoints**

Add the new checkpoint names to the existing `--stop-after` sentence:

```text
Use `--stop-after content-batch`, `--stop-after next-content-batch`, or `--stop-after replace-current-rel` depending on how far you want the local smoke to run.
```

- [ ] **Step 3: Run docs validation after the docs edit**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected: PASS.

### Task 4: Final Verification

**Files:**
- Read: `code_review.md`
- Verify: `scripts/run_branch_cycle_smoke.py`, `tests/test_branch_cycle_smoke_runner.py`, `docs/testing.md`

- [ ] **Step 1: Run branch-cycle regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_tdd_branch_cycle.py tests/test_branch_cycle_smoke_runner.py
```

Expected: PASS.

- [ ] **Step 2: Run docs validation**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected: PASS.

- [ ] **Step 3: Review the diff**

Run:

```powershell
git diff -- scripts\run_branch_cycle_smoke.py tests\test_branch_cycle_smoke_runner.py docs\testing.md
```

Expected: only smoke runner, focused test, and testing documentation changes are present. No branch service semantics are changed.
