from __future__ import annotations

import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from app.services.branch.models import BranchRef
from app.db import get_db_path, init_db
from app.demo_fixtures import SAMPLES
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.jobs import JobService
from app.services.variant.bindings import BindingCommandService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService

DEMO_ROOT = Path("data/demo_samples")
DEMO_ROOT_ENV_VAR = "MOMO_TMS_DEMO_ROOT"


def get_demo_root(path: Path | str | None = None) -> Path:
    if path is not None:
        return Path(path)
    override = os.getenv(DEMO_ROOT_ENV_VAR)
    if override:
        return Path(override)
    return DEMO_ROOT


class DemoService:
    def __init__(self) -> None:
        self.jobs = JobService()
        self.projects = ProjectService()
        self.entries = EntryService()
        self.binding_commands = BindingCommandService()
        self.catalog = VariantCatalogService()

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
        demo_root = get_demo_root()
        db_path = get_db_path()
        self.jobs.clear_storage()
        if demo_root.exists():
            shutil.rmtree(demo_root)
        if db_path.exists():
            db_path.unlink()
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
        root = get_demo_root() / sample_id
        return {
            "root": str(root),
            "import_dir": str(root / "import_bundle"),
            "fill_dir": str(root / "fill_source"),
        }

    def _seed_strings(self, sample: dict[str, Any], project_id: int = DEFAULT_PROJECT_ID) -> None:
        for item in sample["seed_strings"]:
            entry = self.entries.get_or_create_entry(item["business_key"], project_id=project_id)
            string_id = self.catalog.create_variant(
                int(entry["entry_id"]),
                self.catalog.build_content(
                    item.get("file_name"),
                    item["source"],
                    item.get("translations", {}),
                    item.get("remarks", {}),
                ),
            )
            for membership in item.get("memberships", []):
                if membership == "rel":
                    self.binding_commands.bind_scope(int(entry["entry_id"]), BranchRef.rel_current(), string_id)
                elif membership.startswith("dev:"):
                    self.binding_commands.bind_scope(
                        int(entry["entry_id"]),
                        BranchRef.dev(membership.split(":", 1)[1]),
                        string_id,
                    )

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
