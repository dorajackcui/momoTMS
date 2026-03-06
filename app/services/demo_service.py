from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from app.db import DB_PATH, get_conn, init_db
from app.demo_fixtures import SAMPLES
from app.services.branch_service import BranchService
from app.services.job_service import JobService
from app.services.snapshot_service import SnapshotService
from app.services.utils import src_hash

DEMO_ROOT = Path("data/demo_samples")


class DemoService:
    def __init__(self) -> None:
        self.branches = BranchService()
        self.jobs = JobService()
        self.snapshots = SnapshotService()

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
        dev_snapshot = self.snapshots.create_snapshot(
            "dev",
            "demo_seed",
            meta={"sample_id": seed_sample["sample_id"], "label": "Initial dev head"},
        )
        release_snapshot = self._seed_snapshot(
            branch="release",
            action_type="demo_seed",
            items=seed_sample["release_seed"],
            meta={"sample_id": seed_sample["sample_id"], "version": "2.3.0"},
        )
        master_snapshot = self._seed_snapshot(
            branch="master",
            action_type="demo_seed",
            items=seed_sample["master_seed"],
            meta={"sample_id": seed_sample["sample_id"], "version": "master-2026.01"},
        )
        self.branches.set_head("dev", dev_snapshot)
        self.branches.set_head("release", release_snapshot)
        self.branches.set_head("master", master_snapshot)

        return {
            "sample_id": seed_sample["sample_id"],
            "branch_heads": {
                "dev": dev_snapshot,
                "release": release_snapshot,
                "master": master_snapshot,
            },
        }

    def sample_paths(self, sample_id: str) -> dict[str, str]:
        root = DEMO_ROOT / sample_id
        return {
            "root": str(root),
            "import_dir": str(root / "import_bundle"),
            "fill_dir": str(root / "fill_source"),
        }

    def _seed_snapshot(
        self,
        branch: str,
        action_type: str,
        items: list[dict[str, Any]],
        meta: dict[str, Any],
    ) -> int:
        snapshot_id = self.snapshots.create_snapshot(
            branch=branch,
            action_type=action_type,
            meta=meta,
        )
        for item in items:
            entry_id = self._insert_entry(item["key"], item["src"], item.get("version_tag"), item.get("targets", {}))
            self.snapshots.set_item(snapshot_id, item["key"], entry_id, src_hash(item["src"]))
        return snapshot_id

    def _insert_entry(self, key: str, src: str, version_tag: str | None, targets: dict[str, str]) -> int:
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO entries(key, src, src_hash, version_tag, meta_json)
                VALUES (?, ?, ?, ?, '{}')
                """,
                (key, src, src_hash(src), version_tag),
            )
            entry_id = int(cur.lastrowid)
            for lang, target_text in targets.items():
                conn.execute(
                    """
                    INSERT INTO translations(entry_id, lang, target_text, updated_at)
                    VALUES (?, ?, ?, datetime('now'))
                    """,
                    (entry_id, lang, target_text),
                )
        return entry_id

    def _serialize_sample(self, spec: dict[str, Any]) -> dict[str, Any]:
        sample = deepcopy(spec)
        sample.pop("release_seed", None)
        sample.pop("master_seed", None)
        sample.pop("import_workbooks", None)
        sample.pop("fill_workbooks", None)
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
