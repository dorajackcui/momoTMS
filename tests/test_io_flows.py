from pathlib import Path

from app.db import get_db_path
from app.services.demo.service import DemoService
from app.services.workflows.fill import FillService


def reset_demo() -> dict:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    DemoService().reset()
    return DemoService().get_sample("core-cycle")


def test_fill_reads_release_branch_bindings() -> None:
    sample = reset_demo()
    output_zip = Path(sample["paths"]["root"]) / "filled.zip"
    result = FillService().fill_and_export(
        sample["paths"]["fill_dir"],
        str(output_zip),
        sample["lang"],
    )

    statuses = {row["business_key"]: row["status"] for row in result["report_rows"] if row.get("business_key")}
    assert statuses["common.welcome"] == "FILLED"
    assert statuses["fill.master_only"] == "MISSING_KEY_IN_BASE"
    assert statuses["fill.rel"] == "SRC_MISMATCH"
    assert output_zip.exists()
