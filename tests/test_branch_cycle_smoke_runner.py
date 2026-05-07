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


def test_smoke_runner_default_content_progress_interval_is_5000() -> None:
    args = run_branch_cycle_smoke.build_parser().parse_args([])

    assert args.content_progress_interval == 5000


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
