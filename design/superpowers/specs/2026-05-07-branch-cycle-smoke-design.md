# Branch Cycle Smoke Workflow Expansion Design

## Purpose

Expand `scripts/run_branch_cycle_smoke.py` so local large-workbook smoke runs cover the current branch cycle more closely:

- seed `rel/current` from the release workbook
- create and update two dev branches
- replace `rel/current` from the final dev branch after its content mutation completes

## Scope

The change is limited to the smoke runner and its documented invocation guidance. It does not change branch, mutation, bootstrap, replace, workbook parsing, or database semantics.

## CLI Contract

Keep existing arguments working. Add:

- `--next-dev-version`, default `2.5.4`
- `--next-dev-workbook`, optional path for the second dev branch workbook

If `--next-dev-workbook` is omitted, the runner reuses `--dev-workbook` for the second dev branch. This lets the current command continue to exercise the expanded workflow while still allowing a distinct second workbook when available.

## Workflow

The runner will execute these checkpoints in order:

1. Create the isolated project.
2. Bulk seed `rel/current`.
3. Bootstrap the first dev branch from `--dev-workbook`.
4. Apply content mutation to the first dev branch from `--dev-workbook`.
5. Bootstrap the second dev branch from `--next-dev-workbook` or the reused dev workbook.
6. Apply content mutation to the second dev branch from that same second workbook.
7. Execute branch replace from the second dev branch to `rel/current`.

Each dev branch cycle should reuse the existing workbook-copy, batch-create, bootstrap, content-batch, and content-mutation behavior so timing and summary output stay familiar.

## Stop Points And Output

Extend `--stop-after` with second-dev and replace checkpoints:

- `next-bootstrap-batch`
- `next-bootstrap`
- `next-content-batch`
- `next-content-mutation`
- `replace-current-rel`

Keep existing summary printing and stage timing output. Print labels that include the branch ref so it is clear which dev cycle produced each summary.

## Error Handling

Validate the second workbook path after resolving defaults. Invalid paths should fail early with a clear `FileNotFoundError`, matching the existing release/dev workbook behavior.

Use `BranchReplaceService.execute(next_dev_ref, BranchRef.rel_current(), project_id=project_id)` directly after the second content mutation. If replace fails, the script should surface the original exception and return non-zero through the existing top-level error handling.

## Documentation And Verification

Update `docs/testing.md` to describe the two-dev smoke flow and the optional second workbook argument.

Verify with:

- `.\.venv\Scripts\python.exe -m pytest -q tests/test_tdd_branch_cycle.py`
- `.\.venv\Scripts\python.exe scripts\validate_docs.py`

Running the large-workbook smoke script itself requires local workbook files, so it should be reported as not run unless those paths are provided and available.
