from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from app.db import DB_PATH, init_db
from app.demo_fixtures import SAMPLES
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.jobs import JobService
from app.services.variant.compatibility import StringService

DEMO_ROOT = Path("data/demo_samples")


class DemoService:
    def __init__(self) -> None:
        self.jobs = JobService()
        self.projects = ProjectService()
        self.strings = StringService()

    def list_samples(self) -> list[dict[str, Any]]:
        return [self._serialize_sample(spec) for spec in SAMPLES]

    def get_sample(self, sample_id: str) -> dict[str, Any]:
        for spec in SAMPLES:
            if spec["sample_id"] == sample_id:
                sample = self._serialize_sample(spec)
                sample["paths"] = self.sample_paths(sample_id)
                return sample
        raise KeyError(f"unknown sample: {sample_id}")

    def ensure_sample_files(self) -> None:
        for spec in SAMPLES:
            self._build_sample_files(spec)

    def reset(self) -> dict[str, Any]:
        self.jobs.clear_storage()
        if DEMO_ROOT.exists():
            shutil.rmtree(DEMO_ROOT)
        if DB_PATH.exists():
            DB_PATH.unlink()
        init_db()
        self.ensure_sample_files()
        seed_sample = SAMPLES[0]
        project = self.projects.create_project(
            "Demo Project",
            ["fr", "en"],
            ["context"],
        )
        self._seed_strings(seed_sample, project_id=int(project["project_id"]))
        return {"sample_id": seed_sample["sample_id"]}

    def sample_paths(self, sample_id: str) -> dict[str, str]:
        root = DEMO_ROOT / sample_id
        return {
            "root": str(root),
            "import_dir": str(root / "import_bundle"),
            "fill_dir": str(root / "fill_source"),
        }

    def _seed_strings(self, sample: dict[str, Any], project_id: int = DEFAULT_PROJECT_ID) -> None:
        for item in sample["seed_strings"]:
            string_id = self.strings.create_string(
                business_key=item["business_key"],
                file_name=item.get("file_name"),
                source=item["source"],
                translations=item.get("translations", {}),
                remarks=item.get("remarks", {}),
                project_id=project_id,
            )
            for membership in item.get("memberships", []):
                if membership == "rel":
                    self.strings.ensure_membership(string_id, "rel", "current")
                elif membership.startswith("dev:"):
                    self.strings.ensure_membership(string_id, "dev", membership.split(":", 1)[1])

    def _serialize_sample(self, spec: dict[str, Any]) -> dict[str, Any]:
        sample = deepcopy(spec)
        sample.pop("seed_strings", None)
        sample.pop("import_workbooks", None)
        sample.pop("fill_workbooks", None)
        sample["paths"] = self.sample_paths(spec["sample_id"])
        return sample

    def _build_sample_files(self, spec: dict[str, Any]) -> None:
        paths = self.sample_paths(spec["sample_id"])
        import_root = Path(paths["import_dir"])
        fill_root = Path(paths["fill_dir"])
        import_root.mkdir(parents=True, exist_ok=True)
        fill_root.mkdir(parents=True, exist_ok=True)
        for workbook_spec in spec["import_workbooks"]:
            self._write_workbook(import_root / workbook_spec["relative_path"], workbook_spec)
        for workbook_spec in spec["fill_workbooks"]:
            self._write_workbook(fill_root / workbook_spec["relative_path"], workbook_spec)

    def _write_workbook(self, file_path: Path, workbook_spec: dict[str, Any]) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        default_sheet = workbook.active
        for index, sheet_spec in enumerate(workbook_spec["sheets"]):
            sheet = default_sheet if index == 0 else workbook.create_sheet()
            sheet.title = sheet_spec["title"]
            for row in sheet_spec["rows"]:
                sheet.append(row)
        workbook.save(file_path)
